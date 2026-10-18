"""Cross-check logic that must hold for every check, not just the examples tested elsewhere."""

from __future__ import annotations

from collections.abc import Iterator
from itertools import product

import pytest

from shuri.checks.cpu import build_cpu_result
from shuri.checks.disk import build_disk_result
from shuri.checks.memory import build_memory_result
from shuri.checks.physical_drives import build_physical_drive_result
from shuri.core.scoring import assess_health
from shuri.models import CheckResult, CheckStatus
from shuri.models.cpu import CpuSnapshot
from shuri.models.disk import DiskSnapshot
from shuri.models.physical_drive import PhysicalDriveSnapshot

_PERCENTS = tuple(range(0, 101, 5))


def _cpu_results() -> Iterator[CheckResult]:
    for percent in _PERCENTS:
        snapshot = CpuSnapshot("Test CPU", "x64", 4, 8, float(percent), 3000.0)
        yield build_cpu_result(snapshot, None)


def _memory_results() -> Iterator[CheckResult]:
    total = 1000
    for available, swap_used in product(range(0, 1001, 50), (0, 500, 850, 1000)):
        yield build_memory_result(total, available, total - available, 1000, swap_used)
    yield build_memory_result(0, 0, 0, 0, 0)


def _disk_results() -> Iterator[CheckResult]:
    for used, system_used in product(_PERCENTS, _PERCENTS):
        yield build_disk_result(
            [
                DiskSnapshot("C:", "C:\\", "NTFS", 1000, 1000 - used * 10, float(used)),
                DiskSnapshot(
                    "D:", "D:\\", "NTFS", 1000, 1000 - system_used * 10, float(system_used)
                ),
            ],
            "C:\\",
        )
    yield build_disk_result([], "C:\\")


def _drive_results() -> Iterator[CheckResult]:
    healths = ("Healthy", "Warning", "Unhealthy", "Degraded", "Unknown", "")
    operational = ((), ("OK",), ("Degraded",), ("Predictive Failure",), ("OK", "Stressed"))
    temperatures = (None, 30.0, 70.0, 95.0)
    wears = (None, 10.0, 90.0, 100.0)
    for health, status, temperature, wear in product(healths, operational, temperatures, wears):
        drive = PhysicalDriveSnapshot(
            "0", "Test Drive", "SSD", "NVMe", health, status, 10**9, temperature, wear
        )
        yield build_physical_drive_result((drive,))
    yield build_physical_drive_result(())


def _all_results() -> Iterator[CheckResult]:
    yield from _cpu_results()
    yield from _memory_results()
    yield from _disk_results()
    yield from _drive_results()


def _describe(result: CheckResult) -> str:
    return f"{result.name}: {result.status} {result.summary!r} {result.findings!r}"


def test_a_failing_check_always_explains_the_score_impact() -> None:
    for result in _all_results():
        if result.status is CheckStatus.FAIL:
            assert result.deductions, _describe(result)


def test_a_warning_or_failure_never_arrives_without_a_reason() -> None:
    for result in _all_results():
        if result.status in {CheckStatus.WARNING, CheckStatus.FAIL}:
            assert result.findings, _describe(result)


def test_unknown_and_passing_checks_never_reduce_the_score() -> None:
    for result in _all_results():
        if result.status in {CheckStatus.UNKNOWN, CheckStatus.PASS}:
            assert not result.deductions, _describe(result)


@pytest.mark.parametrize("batch", range(4))
def test_score_equals_one_hundred_minus_the_listed_deductions(batch: int) -> None:
    results = tuple(_all_results())[batch::4]
    for start in range(0, len(results), 7):
        group = results[start : start + 7]
        expected = max(0, 100 - sum(item.points for r in group for item in r.deductions))

        assessment = assess_health(group)

        assert assessment.score == expected
        assert 0 <= assessment.score <= 100
