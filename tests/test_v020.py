from __future__ import annotations

from shuri.checks import updates
from shuri.checks.antivirus import _signature_age_days
from shuri.checks.battery import parse_battery_report
from shuri.checks.network import parse_windows_network_configuration
from shuri.cli import _selected_format
from shuri.models import CheckStatus


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


def test_available_updates_produce_transparent_deduction(monkeypatch: object) -> None:
    monkeypatch.setattr(updates, "is_windows", lambda: True)
    monkeypatch.setattr(updates, "pending_reboot", lambda: False)
    monkeypatch.setattr(updates, "available_update_count", lambda: 2)

    result = updates.check_updates()

    assert result.status is CheckStatus.WARNING
    assert result.deductions[0].points == 3
    assert "2 Windows update(s) are available." in result.findings


def test_doctor_format_shortcut_accepts_a_single_format() -> None:
    assert _selected_format("html", False, False, False) == "html"
