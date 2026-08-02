from __future__ import annotations

from shuri.checks.physical_drives import build_physical_drive_result, parse_physical_drives
from shuri.models import CheckStatus
from shuri.models.physical_drive import PhysicalDriveSnapshot


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
