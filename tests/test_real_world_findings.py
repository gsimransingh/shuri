"""Regression tests for issues found by running Shuri on a real Windows PC."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from rich.console import Console

from shuri.checks import antivirus, eventlogs
from shuri.checks.eventlogs import group_event_incidents, parse_event_levels
from shuri.models import CheckResult, CheckStatus
from shuri.reporters.terminal import _metric_label, show_check_details
from shuri.utils.platform import CommandResult

_BASE = datetime(2026, 10, 18, 11, 13, 42, tzinfo=UTC)


def _event(
    seconds: float, event_id: int = 3, provider: str = "FilterManager", level: int = 2
) -> dict[str, object]:
    stamp = (_BASE + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")
    return {"Level": level, "Id": event_id, "ProviderName": provider, "TimeCreated": stamp}


def _run_check(monkeypatch: pytest.MonkeyPatch, events: list[dict[str, object]]) -> CheckResult:
    monkeypatch.setattr(eventlogs, "is_windows", lambda: True)
    monkeypatch.setattr(
        eventlogs, "run_powershell", lambda *_a, **_k: CommandResult(json.dumps(events))
    )
    return eventlogs.check_event_logs()


def test_boot_burst_of_identical_errors_is_one_incident(monkeypatch: pytest.MonkeyPatch) -> None:
    burst = [_event(index * 0.02) for index in range(35)]
    others = [_event(3600 * hour, event_id=100 + hour, provider="Other") for hour in range(3)]

    result = _run_check(monkeypatch, burst + others)

    assert result.metrics["errors"] == 38
    assert result.metrics["error_incidents"] == 4
    assert result.status is CheckStatus.PASS
    assert result.deductions == ()
    counts = {event["event_id"]: event["count"] for event in result.metrics["recent_events"]}
    assert counts[3] == 35


def test_many_distinct_incidents_still_deduct(monkeypatch: pytest.MonkeyPatch) -> None:
    events = [_event(3600 * hour, event_id=hour) for hour in range(5)]

    result = _run_check(monkeypatch, events)

    assert result.status is CheckStatus.WARNING
    assert result.deductions[0].points == 5
    assert "5 separate System error incident(s)" in result.findings[0]


def test_steady_repeating_fault_is_not_hidden_by_grouping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [_event(30 * index) for index in range(40)]  # one error every 30s for 20 minutes

    result = _run_check(monkeypatch, events)

    assert result.metrics["error_incidents"] >= 5
    assert result.status is CheckStatus.WARNING


def test_same_event_id_at_different_levels_is_not_merged() -> None:
    payload = json.dumps([_event(0, level=2), _event(1, level=3)])

    assert {incident["level"] for incident in group_event_incidents(payload)} == {
        "Error",
        "Warning",
    }


def test_events_without_timestamps_are_never_merged() -> None:
    payload = json.dumps([{"Level": 2, "Id": 1, "ProviderName": "P"}] * 3)

    assert len(group_event_incidents(payload)) == 3


@pytest.mark.parametrize("level", ([2], {"a": 1}, True, 2.5, "2", None, 9))
def test_unrecognised_event_levels_are_ignored_not_fatal(
    monkeypatch: pytest.MonkeyPatch, level: object
) -> None:
    payload = json.dumps([{"Level": level, "Id": 1}])

    assert parse_event_levels(payload) == (0, 0, 0, False)
    assert group_event_incidents(payload) == ()
    assert _run_check(monkeypatch, [{"Level": level, "Id": 1}]).status is CheckStatus.PASS


def test_incident_details_are_bounded_and_newest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    events = [_event(3600 * index, event_id=index) for index in range(60)]

    details = _run_check(monkeypatch, events).metrics["recent_events"]

    assert len(details) == 25
    assert details[0]["time_created"] > details[-1]["time_created"]


def test_defender_timestamp_is_shown_as_readable_iso_not_raw_powershell_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    payload = json.dumps(
        {
            "AMServiceEnabled": True,
            "AntivirusEnabled": True,
            "RealTimeProtectionEnabled": True,
            "AntivirusSignatureLastUpdated": f"/Date({now_ms})/",
        }
    )
    monkeypatch.setattr(antivirus, "is_windows", lambda: True)
    monkeypatch.setattr(antivirus, "run_powershell", lambda *_a, **_k: CommandResult(payload))

    result = antivirus.check_antivirus()

    shown = result.metrics["defender"]["AntivirusSignatureLastUpdated"]
    assert "/Date(" not in shown
    assert datetime.fromisoformat(shown).tzinfo is not None
    assert result.status is CheckStatus.PASS
    assert result.metrics["signature_age_days"] == 0


def test_stale_defender_signatures_are_still_detected_from_powershell_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_ms = int((datetime.now(UTC) - timedelta(days=30)).timestamp() * 1000)
    payload = json.dumps(
        {
            "AMServiceEnabled": True,
            "AntivirusEnabled": True,
            "RealTimeProtectionEnabled": True,
            "AntivirusSignatureLastUpdated": f"/Date({old_ms})/",
        }
    )
    monkeypatch.setattr(antivirus, "is_windows", lambda: True)
    monkeypatch.setattr(antivirus, "run_powershell", lambda *_a, **_k: CommandResult(payload))

    result = antivirus.check_antivirus()

    assert result.status is CheckStatus.WARNING
    assert "30 days old" in result.summary


@pytest.mark.parametrize(
    ("key", "expected"),
    (
        ("AMServiceEnabled", "AM Service Enabled"),
        ("AntivirusSignatureLastUpdated", "Antivirus Signature Last Updated"),
        ("RealTimeProtectionEnabled", "Real Time Protection Enabled"),
        ("dns_servers", "DNS Servers"),
        ("total_bytes", "Total"),
        ("signature_age_days", "Signature Age Days"),
        ("tcp_probe", "TCP Probe"),
    ),
)
def test_metric_labels_are_readable(key: str, expected: str) -> None:
    assert _metric_label(key) == expected


def test_defender_details_render_with_readable_labels() -> None:
    result = CheckResult(
        "antivirus",
        "Antivirus",
        CheckStatus.PASS,
        "ok",
        metrics={"defender": {"AMServiceEnabled": True, "AntivirusSignatureLastUpdated": "x"}},
    )
    console = Console(record=True, width=120, color_system=None)

    show_check_details(result, console)

    rendered = console.export_text()
    assert "AM Service Enabled" in rendered
    assert "Amserviceenabled" not in rendered
