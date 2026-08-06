"""Read-only physical-drive health and reliability diagnostics on Windows."""

from __future__ import annotations

import json
from typing import Any

from shuri.core.policy import DEFAULT_POLICY
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.models.physical_drive import PhysicalDriveSnapshot
from shuri.utils.platform import (
    CommandResult,
    OperatingSystem,
    command_failure_message,
    operating_system,
    run_powershell,
)

_FAIL_HEALTH = {"unhealthy", "critical", "failed", "failure"}
_WARN_HEALTH = {"warning", "degraded"}
_FAIL_OPERATIONAL = {
    "error",
    "lost communication",
    "non-recoverable error",
    "predictive failure",
    "supporting entity in error",
}
_WARN_OPERATIONAL = {"degraded", "no contact", "stressed"}


def parse_physical_drives(payload: str) -> tuple[PhysicalDriveSnapshot, ...]:
    """Parse the bounded JSON payload emitted by the Windows storage query."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return ()
    entries = data if isinstance(data, list) else [data]
    snapshots: list[PhysicalDriveSnapshot] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        device_id = entry.get("DeviceId")
        model = entry.get("FriendlyName")
        size_bytes = entry.get("SizeBytes")
        if (
            not isinstance(device_id, str)
            or not isinstance(model, str)
            or isinstance(size_bytes, bool)
            or not isinstance(size_bytes, int)
            or size_bytes < 0
        ):
            continue
        operational = entry.get("OperationalStatus", [])
        operational_status: tuple[str, ...]
        if isinstance(operational, str):
            operational_status = (operational,)
        elif isinstance(operational, list):
            operational_status = tuple(item for item in operational if isinstance(item, str))
        else:
            operational_status = ()
        snapshots.append(
            PhysicalDriveSnapshot(
                device_id=device_id,
                model=model,
                media_type=_text(entry.get("MediaType")),
                bus_type=_text(entry.get("BusType")),
                health_status=_text(entry.get("HealthStatus")),
                operational_status=operational_status,
                size_bytes=size_bytes,
                temperature_celsius=_number(entry.get("TemperatureCelsius")),
                wear_percent=_number(entry.get("WearPercent")),
                read_errors_total=_integer(entry.get("ReadErrorsTotal")),
                write_errors_total=_integer(entry.get("WriteErrorsTotal")),
                power_on_hours=_integer(entry.get("PowerOnHours")),
            )
        )
    return tuple(snapshots)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else "Unknown"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _physical_drive_snapshots() -> tuple[tuple[PhysicalDriveSnapshot, ...], CommandResult]:
    script = """
    $items = @(
        Get-PhysicalDisk -ErrorAction Stop | ForEach-Object {
            $disk = $_
            $reliability = $null
            try {
                $reliability = $disk | Get-StorageReliabilityCounter -ErrorAction Stop
            } catch {}
            [PSCustomObject]@{
                DeviceId = [string]$disk.DeviceId
                FriendlyName = [string]$disk.FriendlyName
                MediaType = [string]$disk.MediaType
                BusType = [string]$disk.BusType
                HealthStatus = [string]$disk.HealthStatus
                OperationalStatus = @($disk.OperationalStatus | ForEach-Object { [string]$_ })
                SizeBytes = [long]$disk.Size
                TemperatureCelsius = if ($reliability) { $reliability.Temperature } else { $null }
                WearPercent = if ($reliability) { $reliability.Wear } else { $null }
                ReadErrorsTotal = if ($reliability) { $reliability.ReadErrorsTotal } else { $null }
                WriteErrorsTotal = if ($reliability) {
                    $reliability.WriteErrorsTotal
                } else { $null }
                PowerOnHours = if ($reliability) { $reliability.PowerOnHours } else { $null }
            }
        }
    )
    $items | ConvertTo-Json -Depth 4 -Compress
    """
    result = run_powershell(script, timeout=10)
    return (parse_physical_drives(result.output) if result.succeeded else ()), result


def _drive_state(drive: PhysicalDriveSnapshot) -> CheckStatus:
    health = drive.health_status.casefold()
    operational = {value.casefold() for value in drive.operational_status}
    if health in _FAIL_HEALTH or operational & _FAIL_OPERATIONAL:
        return CheckStatus.FAIL
    if (
        health in _WARN_HEALTH
        or operational & _WARN_OPERATIONAL
        or (
            drive.temperature_celsius is not None
            and drive.temperature_celsius >= DEFAULT_POLICY.high_drive_temperature_celsius
        )
        or (
            drive.wear_percent is not None
            and drive.wear_percent >= DEFAULT_POLICY.high_drive_wear_percent
        )
    ):
        return CheckStatus.WARNING
    if health == "healthy" and (not operational or operational <= {"ok"}):
        return CheckStatus.PASS
    return CheckStatus.UNKNOWN


def build_physical_drive_result(
    drives: tuple[PhysicalDriveSnapshot, ...],
    platform_name: str = "Windows",
) -> CheckResult:
    """Assess trustworthy drive states without inferring health from missing counters."""
    states = tuple(_drive_state(drive) for drive in drives)
    failed = tuple(
        drive for drive, state in zip(drives, states, strict=True) if state is CheckStatus.FAIL
    )
    warned = tuple(
        drive for drive, state in zip(drives, states, strict=True) if state is CheckStatus.WARNING
    )
    unknown = tuple(
        drive for drive, state in zip(drives, states, strict=True) if state is CheckStatus.UNKNOWN
    )
    findings: list[str] = []
    deductions: tuple[ScoreDeduction, ...] = ()
    if failed:
        status = CheckStatus.FAIL
        findings.extend(
            f"{drive.model} reports an unhealthy physical-drive state." for drive in failed
        )
        deductions = (
            ScoreDeduction(
                "A physical drive reports an unhealthy state",
                DEFAULT_POLICY.physical_drive_failure_points,
                "physical_drives",
            ),
        )
    elif warned:
        status = CheckStatus.WARNING
        findings.extend(f"{drive.model} reports degraded reliability evidence." for drive in warned)
        deductions = (
            ScoreDeduction(
                "A physical drive reports degraded reliability evidence",
                DEFAULT_POLICY.physical_drive_warning_points,
                "physical_drives",
            ),
        )
    elif drives and len(unknown) == len(drives):
        status = CheckStatus.UNKNOWN
        findings.append(
            f"{platform_name} did not expose a trustworthy health state for any physical drive."
        )
    elif unknown:
        status = CheckStatus.WARNING
        findings.append(
            f"Health evidence was unavailable for {len(unknown)} of "
            f"{len(drives)} physical drive(s)."
        )
    else:
        status = CheckStatus.PASS
    known = len(drives) - len(unknown)
    return CheckResult(
        name="physical_drives",
        title="Physical Drives",
        status=status,
        summary=f"Checked {len(drives)} physical drive(s); {known} had trustworthy health state.",
        metrics={
            "physical_drives": [
                {
                    "device_id": drive.device_id,
                    "model": drive.model,
                    "media_type": drive.media_type,
                    "bus_type": drive.bus_type,
                    "health_status": drive.health_status,
                    "operational_status": list(drive.operational_status),
                    "size_bytes": drive.size_bytes,
                    "temperature_celsius": drive.temperature_celsius,
                    "wear_percent": drive.wear_percent,
                    "read_errors_total": drive.read_errors_total,
                    "write_errors_total": drive.write_errors_total,
                    "power_on_hours": drive.power_on_hours,
                }
                for drive in drives
            ]
        },
        findings=tuple(findings),
        deductions=deductions,
    )


def check_physical_drives() -> CheckResult:
    """Collect and assess physical-drive health without changing storage state."""
    active_os = operating_system()
    if active_os is OperatingSystem.LINUX:
        from shuri.checks.native_unix import check_linux_drives

        return check_linux_drives()
    if active_os is OperatingSystem.MACOS:
        from shuri.checks.native_unix import check_macos_drives

        return check_macos_drives()
    if active_os is not OperatingSystem.WINDOWS:
        from shuri.checks.native_unix import unsupported_native_check

        return unsupported_native_check("physical_drives", "Physical Drives", active_os)
    drives, result = _physical_drive_snapshots()
    if not result.succeeded:
        return CheckResult(
            name="physical_drives",
            title="Physical Drives",
            status=CheckStatus.UNKNOWN,
            summary=command_failure_message("Windows physical-drive query", result),
        )
    if not drives:
        return CheckResult(
            name="physical_drives",
            title="Physical Drives",
            status=CheckStatus.UNKNOWN,
            summary="Windows returned no valid physical-drive health data.",
        )
    return build_physical_drive_result(drives)
