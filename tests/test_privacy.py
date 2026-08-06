from __future__ import annotations

from shuri.core.privacy import redact_report
from shuri.models import CheckResult, CheckStatus, Report
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
                            "name": "Ethernet",
                            "addresses": ["192.168.1.5"],
                            "mac_address": "00:11:22:33:44:55",
                        }
                    ],
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
    ):
        assert sensitive not in rendered


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
