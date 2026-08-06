from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

from shuri import cli
from shuri.checks import updates
from shuri.checks.antivirus import _signature_age_days
from shuri.checks.battery import parse_battery_report
from shuri.checks.eventlogs import parse_event_levels
from shuri.checks.network import parse_windows_network_configuration
from shuri.cli import _selected_format
from shuri.models import CheckStatus
from shuri.utils.platform import OperatingSystem


def test_windows_network_configuration_extracts_gateway_and_dns() -> None:
    gateway, dns_servers = parse_windows_network_configuration(
        '[{"Gateway":["192.168.1.1"],"DnsServers":["1.1.1.1","8.8.8.8"]}]'
    )

    assert gateway == "192.168.1.1"
    assert dns_servers == ("1.1.1.1", "8.8.8.8")


def test_battery_report_extracts_capacities() -> None:
    report = "DESIGN CAPACITY</td><td>80,000 mWh FULL CHARGE CAPACITY</td><td>64,000 mWh"

    assert parse_battery_report(report) == (80_000, 64_000)


def test_signature_age_recognises_parseable_and_invalid_dates() -> None:
    assert _signature_age_days("2020-01-01T00:00:00Z") is not None
    assert _signature_age_days("not-a-date") is None


def test_signature_age_recognises_windows_powershell_json_dates() -> None:
    three_days_ago = datetime.now(UTC) - timedelta(days=3)
    timestamp_ms = int(three_days_ago.timestamp() * 1000)

    assert _signature_age_days(f"/Date({timestamp_ms})/") == 3
    assert _signature_age_days(f"/Date({timestamp_ms}+0530)/") == 3


def test_available_updates_produce_transparent_deduction(monkeypatch: object) -> None:
    monkeypatch.setattr(updates, "operating_system", lambda: OperatingSystem.WINDOWS)
    monkeypatch.setattr(updates, "pending_reboot", lambda: False)
    monkeypatch.setattr(updates, "available_update_count", lambda: (2, None))

    result = updates.check_updates()

    assert result.status is CheckStatus.WARNING
    assert result.deductions[0].points == 3
    assert "2 Windows update(s) are available." in result.findings


def test_doctor_format_shortcut_accepts_a_single_format() -> None:
    assert _selected_format("html", False, False, False) == "html"


def test_structured_event_levels_expose_truncation() -> None:
    payload = "[" + ",".join('{"Level":2}' for _ in range(51)) + "]"

    assert parse_event_levels(payload) == (0, 50, 0, True)


def test_redaction_requires_an_export_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "_build_report",
        lambda *args, **kwargs: pytest.fail("scan should not start for invalid options"),
    )

    result = CliRunner().invoke(cli.app, ["doctor", "--redact"])

    assert result.exit_code != 0
    assert "requires an exported report format" in result.output
