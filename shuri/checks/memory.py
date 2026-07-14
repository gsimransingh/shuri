"""Memory and swap pressure diagnostics."""

from __future__ import annotations

import psutil

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.constants import CRITICAL_MEMORY_PERCENT, LOW_MEMORY_PERCENT


def build_memory_result(
    total_bytes: int,
    available_bytes: int,
    used_bytes: int,
    swap_total_bytes: int,
    swap_used_bytes: int,
) -> CheckResult:
    """Assess memory values without collecting them, for reliable testing."""
    available_percent = (available_bytes / total_bytes * 100) if total_bytes else 0.0
    swap_percent = (swap_used_bytes / swap_total_bytes * 100) if swap_total_bytes else 0.0
    status = CheckStatus.PASS
    deductions: list[ScoreDeduction] = []
    findings: list[str] = []
    if available_percent < CRITICAL_MEMORY_PERCENT:
        status = CheckStatus.FAIL
        findings.append("Available memory is critically low.")
        deductions.append(ScoreDeduction("Available memory is below 10%", 10, "memory"))
    elif available_percent < LOW_MEMORY_PERCENT:
        status = CheckStatus.WARNING
        findings.append("Available memory is low.")
        deductions.append(ScoreDeduction("Available memory is below 20%", 5, "memory"))
    if swap_percent >= 80:
        status = CheckStatus.FAIL if status is CheckStatus.PASS else status
        findings.append("Swap or page file use is very high.")
        deductions.append(ScoreDeduction("Swap or page file use is above 80%", 5, "memory"))
    return CheckResult(
        name="memory",
        title="Memory",
        status=status,
        summary=f"{available_percent:.1f}% of memory is available.",
        metrics={
            "total_bytes": total_bytes,
            "available_bytes": available_bytes,
            "used_bytes": used_bytes,
            "available_percent": round(available_percent, 1),
            "swap_total_bytes": swap_total_bytes,
            "swap_used_bytes": swap_used_bytes,
            "swap_percent": round(swap_percent, 1),
        },
        findings=tuple(findings),
        deductions=tuple(deductions),
    )


def check_memory() -> CheckResult:
    """Collect physical memory and swap usage."""
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return build_memory_result(memory.total, memory.available, memory.used, swap.total, swap.used)
