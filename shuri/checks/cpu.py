"""CPU collection and pressure assessment."""

from __future__ import annotations

import os
import platform

import psutil

from shuri.checks.processes import attach_process_attribution, collect_cpu_process_attribution
from shuri.core.policy import DEFAULT_POLICY
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.models.cpu import CpuSnapshot


def build_cpu_result(
    snapshot: CpuSnapshot, load_average: tuple[float, float, float] | None
) -> CheckResult:
    """Assess a CPU snapshot; kept pure to make threshold logic easy to test."""
    deductions: list[ScoreDeduction] = []
    findings: list[str] = []
    status = CheckStatus.PASS
    if snapshot.utilisation_percent >= DEFAULT_POLICY.critical_cpu_percent:
        status = CheckStatus.FAIL
        findings.append("CPU usage is critically high.")
        deductions.append(
            ScoreDeduction("CPU usage is above 95%", DEFAULT_POLICY.critical_cpu_points, "cpu")
        )
    elif snapshot.utilisation_percent >= DEFAULT_POLICY.high_cpu_percent:
        status = CheckStatus.WARNING
        findings.append("CPU usage is elevated.")
        deductions.append(
            ScoreDeduction("CPU usage is above 85%", DEFAULT_POLICY.high_cpu_points, "cpu")
        )
    metrics: dict[str, object] = {
        "model": snapshot.model or "Unavailable",
        "architecture": snapshot.architecture,
        "physical_cores": snapshot.physical_cores,
        "logical_cores": snapshot.logical_cores,
        "utilisation_percent": snapshot.utilisation_percent,
        "frequency_mhz": snapshot.frequency_mhz,
        "load_average": load_average,
    }
    return CheckResult(
        name="cpu",
        title="CPU",
        status=status,
        summary=f"CPU utilisation is {snapshot.utilisation_percent:.1f}%.",
        metrics=metrics,
        findings=tuple(findings),
        deductions=tuple(deductions),
    )


def check_cpu() -> CheckResult:
    """Collect a short CPU usage sample and hardware basics."""
    frequency_collector = getattr(psutil, "cpu_freq", None)
    frequency = frequency_collector() if frequency_collector else None
    snapshot = CpuSnapshot(
        model=platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", ""),
        architecture=platform.machine(),
        physical_cores=psutil.cpu_count(logical=False),
        logical_cores=psutil.cpu_count(logical=True),
        utilisation_percent=psutil.cpu_percent(interval=0.2),
        frequency_mhz=frequency.current if frequency else None,
    )
    get_load_average = getattr(os, "getloadavg", None)
    try:
        load_average = get_load_average() if get_load_average else None
    except OSError:
        load_average = None
    result = build_cpu_result(snapshot, load_average)
    if result.status in {CheckStatus.WARNING, CheckStatus.FAIL}:
        return attach_process_attribution(result, collect_cpu_process_attribution())
    return result
