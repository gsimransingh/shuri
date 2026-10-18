from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest

from shuri.checks import cpu, disk, memory, network, services, system
from shuri.core import assess_health
from shuri.core.privacy import IDENTIFIER_KEYS, SAFE_METRIC_KEYS, redact_report
from shuri.models import CheckResult, CheckStatus, Report, ScoreDeduction
from shuri.reporters import render_json


def test_redaction_removes_workstation_and_network_identifiers() -> None:
    report = Report.create(
        (
            CheckResult(
                "network",
                "Network",
                CheckStatus.PASS,
                "Probes succeeded.",
                metrics={
                    "hostname": "private-host",
                    "default_gateway": "192.168.1.1",
                    "dns_servers": ["10.0.0.2"],
                    "tcp_probe": {"target": "internal.example", "succeeded": True},
                    "adapters": [
                        {
                            "name": "Contoso VPN",
                            "addresses": ["192.168.1.5"],
                            "mac_address": "00:11:22:33:44:55",
                        },
                    ],
                    "physical_drives": [{"device_id": "disk-unique-id", "model": "Test NVMe"}],
                },
            ),
        ),
        "private-host",
    )

    rendered = render_json(redact_report(report))

    assert '"redacted": true' in rendered
    for sensitive in (
        "private-host",
        "192.168.1.1",
        "10.0.0.2",
        "internal.example",
        "192.168.1.5",
        "00:11:22:33:44:55",
        "Contoso VPN",
        "disk-unique-id",
    ):
        assert sensitive not in rendered
    assert "Test NVMe" in rendered


def test_redaction_removes_nested_workstation_identifiers() -> None:
    report = Report.create(
        (
            CheckResult(
                "network",
                "Network",
                CheckStatus.WARNING,
                "CPU is elevated.",
                metrics={"owner": {"username": "private-user", "hostname": "private-host"}},
            ),
        ),
        "private-host",
    )

    redacted = redact_report(report)
    rendered = render_json(redacted)

    assert "private-user" not in rendered
    assert "private-host" not in rendered
    assert rendered.count("[redacted]") >= 2
    assert redacted.results[0].status is CheckStatus.WARNING


def test_unreviewed_metric_keys_are_redacted() -> None:
    report = Report.create(
        (
            CheckResult(
                "new_check",
                "New check",
                CheckStatus.PASS,
                "Fine.",
                metrics={"brand_new_field": "secret-value", "total_bytes": 10},
            ),
        ),
        "host-name",
    )

    rendered = render_json(redact_report(report))

    assert "secret-value" not in rendered
    assert '"total_bytes": 10' in rendered


def test_identifiers_are_scrubbed_from_summaries_findings_and_deductions() -> None:
    check = CheckResult(
        "network",
        "Network",
        CheckStatus.WARNING,
        "Adapter Contoso VPN on corp-laptop-07 has no gateway.",
        metrics={
            "hostname": "corp-laptop-07",
            "adapters": [{"name": "Contoso VPN", "mac_address": "00:11:22:33:44:55"}],
        },
        findings=("Reach 192.168.1.1 via Contoso VPN failed.",),
        deductions=(ScoreDeduction("Gateway 192.168.1.1 unreachable", 5, "network"),),
    )
    metrics = dict(check.metrics, default_gateway="192.168.1.1")
    check = replace(check, metrics=metrics)
    report = Report.create((check,), "corp-laptop-07", assess_health((check,)))

    rendered = render_json(redact_report(report))

    for sensitive in ("corp-laptop-07", "Contoso VPN", "192.168.1.1", "00:11:22:33:44:55"):
        assert sensitive.casefold() not in rendered.casefold()


def test_every_metric_key_emitted_by_portable_checks_is_reviewed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(network, "_can_resolve", lambda _host: True)
    monkeypatch.setattr(network, "_can_connect", lambda _host, _port: True)
    monkeypatch.setattr(
        network, "_windows_network_configuration", lambda: ("10.0.0.1", ("1.1.1.1",), None)
    )
    results = [
        check()
        for check in (
            cpu.check_cpu,
            memory.check_memory,
            disk.check_disk,
            system.check_system,
            lambda: network.check_network(probe=True),
        )
    ]

    unreviewed = {
        key
        for result in results
        for key in _all_keys(result.metrics)
        if key not in SAFE_METRIC_KEYS and key not in IDENTIFIER_KEYS
    }

    assert not unreviewed, f"Review these keys for redaction: {sorted(unreviewed)}"


def test_service_names_survive_redaction() -> None:
    assert set(services._SERVICES) <= SAFE_METRIC_KEYS


def _all_keys(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _all_keys(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _all_keys(item)
