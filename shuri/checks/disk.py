"""Mounted filesystem capacity diagnostics."""

from __future__ import annotations

from collections.abc import Iterable

import psutil

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.models.disk import DiskSnapshot
from shuri.utils.constants import CRITICAL_DISK_PERCENT, LOW_DISK_PERCENT
from shuri.utils.platform import system_drive


def build_disk_result(disks: Iterable[DiskSnapshot], system_mount: str) -> CheckResult:
    """Assess disk free space from collected filesystem snapshots."""
    snapshots = tuple(disks)
    if not snapshots:
        return CheckResult(
            name="disk",
            title="Disk",
            status=CheckStatus.UNKNOWN,
            summary="No accessible fixed filesystems were found.",
        )
    status = CheckStatus.PASS
    deductions: list[ScoreDeduction] = []
    findings: list[str] = []
    for disk in snapshots:
        free_percent = 100 - disk.used_percent
        is_system = disk.mountpoint.casefold() == system_mount.casefold()
        if is_system and free_percent < CRITICAL_DISK_PERCENT:
            status = CheckStatus.FAIL
            findings.append(
                f"System drive {disk.mountpoint} has only {free_percent:.1f}% free space."
            )
            deductions.append(ScoreDeduction("System drive is below 10% free", 15, "disk"))
        elif free_percent < CRITICAL_DISK_PERCENT:
            status = CheckStatus.WARNING if status is CheckStatus.PASS else status
            findings.append(f"{disk.mountpoint} has only {free_percent:.1f}% free space.")
            deductions.append(ScoreDeduction(f"{disk.mountpoint} is below 10% free", 5, "disk"))
        elif is_system and free_percent < LOW_DISK_PERCENT:
            status = CheckStatus.WARNING if status is CheckStatus.PASS else status
            findings.append(f"System drive {disk.mountpoint} is running low on free space.")
            deductions.append(ScoreDeduction("System drive is below 15% free", 8, "disk"))
    return CheckResult(
        name="disk",
        title="Disk",
        status=status,
        summary=f"Checked {len(snapshots)} accessible filesystem(s).",
        metrics={
            "filesystems": [
                {
                    "device": disk.device,
                    "mountpoint": disk.mountpoint,
                    "filesystem": disk.filesystem,
                    "total_bytes": disk.total_bytes,
                    "free_bytes": disk.free_bytes,
                    "used_percent": disk.used_percent,
                }
                for disk in snapshots
            ]
        },
        findings=tuple(findings),
        deductions=tuple(deductions),
    )


def check_disk() -> CheckResult:
    """Collect capacity for accessible physical filesystems."""
    snapshots: list[DiskSnapshot] = []
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except OSError:
            continue
        snapshots.append(
            DiskSnapshot(
                device=partition.device,
                mountpoint=partition.mountpoint,
                filesystem=partition.fstype,
                total_bytes=usage.total,
                free_bytes=usage.free,
                used_percent=usage.percent,
            )
        )
    return build_disk_result(snapshots, system_drive())
