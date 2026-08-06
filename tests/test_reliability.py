"""Regression coverage for common Windows workstation edge cases."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from shuri.checks import antivirus, battery, physical_drives, updates
from shuri.models import CheckStatus
from shuri.utils.platform import CommandFailure, CommandResult


def test_update_timeout_is_unknown_without_a_score_deduction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slow Windows Update query must not turn into a failed readiness check."""
    monkeypatch.setattr(updates, "is_windows", lambda: True)
    monkeypatch.setattr(updates, "pending_reboot", lambda: False)
    monkeypatch.setattr(
        updates,
        "available_update_count",
        lambda: (None, CommandResult(failure=CommandFailure.TIMEOUT)),
    )

    result = updates.check_updates()

    assert result.status is CheckStatus.UNKNOWN
    assert result.deductions == ()
    assert "timed out" in result.findings[0]


def test_defender_access_denied_with_third_party_antivirus_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A restricted Defender query must not claim third-party protection is unhealthy."""
    monkeypatch.setattr(antivirus, "is_windows", lambda: True)
    monkeypatch.setattr(
        antivirus,
        "_defender_status",
        lambda: (None, CommandResult(failure=CommandFailure.ACCESS_DENIED)),
    )
    monkeypatch.setattr(antivirus, "_third_party_antivirus_products", lambda: ("Contoso AV",))

    result = antivirus.check_antivirus()

    assert result.status is CheckStatus.UNKNOWN
    assert result.deductions == ()
    assert result.metrics["third_party_products"] == ["Contoso AV"]


def test_battery_report_is_removed_after_a_successful_parse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A successful battery report is parsed and removed from the temporary directory."""
    monkeypatch.setattr(battery, "is_windows", lambda: True)
    monkeypatch.setattr(battery.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(battery, "uuid4", lambda: SimpleNamespace(hex="battery-report"))

    def write_report(command: tuple[str, ...], **_kwargs: object) -> CommandResult:
        Path(command[-1]).write_text(
            "DESIGN CAPACITY</td><td>80,000 mWh FULL CHARGE CAPACITY</td><td>64,000 mWh",
            encoding="utf-8",
        )
        return CommandResult()

    monkeypatch.setattr(battery, "run_command", write_report)

    design, full_charge, health, error = battery._battery_health()

    assert (design, full_charge, health, error) == (80_000, 64_000, 80.0, None)
    assert list(tmp_path.iterdir()) == []


def test_empty_physical_drive_output_is_unknown_without_a_score_deduction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storage Management can succeed without exposing drives; that is not a failed drive."""
    monkeypatch.setattr(physical_drives, "is_windows", lambda: True)
    monkeypatch.setattr(
        physical_drives,
        "_physical_drive_snapshots",
        lambda: ((), CommandResult()),
    )

    result = physical_drives.check_physical_drives()

    assert result.status is CheckStatus.UNKNOWN
    assert result.deductions == ()
    assert "no valid physical-drive health data" in result.summary
