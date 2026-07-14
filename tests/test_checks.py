from __future__ import annotations

from shuri.checks.cpu import build_cpu_result
from shuri.checks.disk import build_disk_result
from shuri.checks.memory import build_memory_result
from shuri.models import CheckStatus
from shuri.models.cpu import CpuSnapshot
from shuri.models.disk import DiskSnapshot


def test_cpu_high_usage_has_a_transparent_deduction() -> None:
    result = build_cpu_result(
        CpuSnapshot("Test CPU", "x86_64", 4, 8, 96.0, 3200.0),
        load_average=None,
    )

    assert result.status is CheckStatus.FAIL
    assert result.deductions[0].points == 10


def test_memory_low_availability_is_a_warning() -> None:
    result = build_memory_result(
        total_bytes=100,
        available_bytes=15,
        used_bytes=85,
        swap_total_bytes=0,
        swap_used_bytes=0,
    )

    assert result.status is CheckStatus.WARNING
    assert result.deductions[0].points == 5


def test_system_drive_low_space_has_stronger_deduction() -> None:
    result = build_disk_result(
        [DiskSnapshot("C:", "C:\\", "NTFS", 100, 5, 95.0)],
        system_mount="C:\\",
    )

    assert result.status is CheckStatus.FAIL
    assert result.deductions[0].points == 15
