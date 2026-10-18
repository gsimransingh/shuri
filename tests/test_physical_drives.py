from __future__ import annotations

import pytest

from shuri.checks import physical_drives
from shuri.checks.physical_drives import build_physical_drive_result, parse_physical_drives
from shuri.models import CheckResult, CheckStatus
from shuri.models.physical_drive import PhysicalDriveSnapshot
from shuri.utils.platform import CommandResult


def _drive(**changes: object) -> PhysicalDriveSnapshot:
    values: dict[str, object] = {
        "device_id": "0",
        "model": "Test NVMe",
        "media_type": "SSD",
        "bus_type": "NVMe",
        "health_status": "Healthy",
        "operational_status": ("OK",),
        "size_bytes": 1_000_000,
    }
    values.update(changes)
    return PhysicalDriveSnapshot(**values)  # type: ignore[arg-type]


def test_parse_physical_drive_accepts_missing_optional_reliability_counters() -> None:
    payload = (
        '{"DeviceId":"0","FriendlyName":"Test NVMe","MediaType":"SSD",'
        '"BusType":"NVMe","HealthStatus":"Healthy","OperationalStatus":["OK"],'
        '"SizeBytes":1000000,"TemperatureCelsius":null,"WearPercent":null}'
    )

    drives = parse_physical_drives(payload)

    assert len(drives) == 1
    assert drives[0].health_status == "Healthy"
    assert drives[0].temperature_celsius is None


def test_healthy_drive_passes_without_optional_counters() -> None:
    result = build_physical_drive_result((_drive(),))

    assert result.status is CheckStatus.PASS
    assert result.deductions == ()


def test_unhealthy_drive_fails_with_one_bounded_deduction() -> None:
    result = build_physical_drive_result(
        (_drive(health_status="Unhealthy", operational_status=("Predictive Failure",)),)
    )

    assert result.status is CheckStatus.FAIL
    assert result.deductions[0].points == 20


def test_hot_or_high_wear_drive_warns() -> None:
    result = build_physical_drive_result((_drive(temperature_celsius=72.0),))

    assert result.status is CheckStatus.WARNING
    assert result.deductions[0].points == 8


def test_unknown_health_is_not_treated_as_healthy() -> None:
    result = build_physical_drive_result(
        (_drive(health_status="Unknown", operational_status=("Unknown",)),)
    )

    assert result.status is CheckStatus.UNKNOWN
    assert result.deductions == ()


def _run_with(
    monkeypatch: pytest.MonkeyPatch, drives: tuple[PhysicalDriveSnapshot, ...]
) -> CheckResult:
    monkeypatch.setattr(physical_drives, "is_windows", lambda: True)
    monkeypatch.setattr(
        physical_drives, "_physical_drive_snapshots", lambda: (drives, CommandResult("ok"))
    )
    return physical_drives.check_physical_drives()


def test_file_backed_virtual_disks_are_not_counted_as_physical_drives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: a mounted VHD was reported as a physical 1 TB SSD."""
    virtual = _drive(device_id="1", model="Msft Virtual Disk", bus_type="File Backed Virtual")

    result = _run_with(monkeypatch, (virtual, _drive()))

    assert result.status is CheckStatus.PASS
    assert result.summary.startswith("Checked 1 physical drive(s)")
    assert result.metrics["virtual_drives_ignored"] == 1
    assert [d["model"] for d in result.metrics["physical_drives"]] == ["Test NVMe"]


def test_unhealthy_virtual_disk_does_not_fail_the_check(monkeypatch: pytest.MonkeyPatch) -> None:
    virtual = _drive(bus_type="Virtual", health_status="Unhealthy")

    result = _run_with(monkeypatch, (virtual, _drive(device_id="2")))

    assert result.status is CheckStatus.PASS


def test_only_virtual_disks_is_unknown_not_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_with(monkeypatch, (_drive(bus_type="File Backed Virtual"),))

    assert result.status is CheckStatus.UNKNOWN
    assert "Only virtual disks" in result.summary


def test_vm_guest_disks_on_a_scsi_bus_are_still_assessed(monkeypatch: pytest.MonkeyPatch) -> None:
    guest = _drive(model="Msft Virtual Disk", bus_type="SAS")

    result = _run_with(monkeypatch, (guest,))

    assert result.metrics["virtual_drives_ignored"] == 0
