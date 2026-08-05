"""Privacy-bounded process resource attribution for elevated diagnostics."""

from __future__ import annotations

import os
from dataclasses import replace
from time import perf_counter, sleep
from typing import Any

import psutil

from shuri.models import CheckResult

MAX_CONTRIBUTORS = 5
MAX_PROCESSES_SCANNED = 2_048
COLLECTION_BUDGET_SECONDS = 0.75
CPU_SAMPLE_SECONDS = 0.1
MAX_PROCESS_NAME_LENGTH = 128

type ProcessAttribution = dict[str, Any]


def collect_cpu_process_attribution(
    *,
    limit: int = MAX_CONTRIBUTORS,
    max_processes: int = MAX_PROCESSES_SCANNED,
    time_budget: float = COLLECTION_BUDGET_SECONDS,
    sample_interval: float = CPU_SAMPLE_SECONDS,
) -> ProcessAttribution:
    """Return a bounded sample of processes using the most CPU."""
    started = perf_counter()
    deadline = started + max(0.0, time_budget)
    reserved_sample = min(max(0.0, sample_interval), max(0.0, time_budget) / 3)
    reserved_measurement = min(0.1, max(0.0, time_budget) / 3)
    priming_deadline = deadline - reserved_sample - reserved_measurement
    sampled: list[tuple[psutil.Process, int, str]] = []
    skipped = 0
    truncated = False
    try:
        for process in psutil.process_iter(attrs=("pid", "name")):
            if len(sampled) >= max_processes or perf_counter() >= priming_deadline:
                truncated = True
                break
            try:
                process_id = _process_id(process.info.get("pid"))
                if process_id is None or process_id == os.getpid():
                    continue
                process_name = _process_name(process.info.get("name"))
                process.cpu_percent(interval=None)
                sampled.append((process, process_id, process_name))
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                skipped += 1
        remaining = deadline - perf_counter()
        if sampled and remaining > 0:
            sleep(min(max(0.0, sample_interval), remaining))
        contributors: list[dict[str, object]] = []
        for process, process_id, process_name in sampled:
            if perf_counter() >= deadline:
                truncated = True
                break
            try:
                cpu_percent = max(0.0, float(process.cpu_percent(interval=None)))
            except (
                psutil.AccessDenied,
                psutil.NoSuchProcess,
                psutil.ZombieProcess,
                TypeError,
                ValueError,
            ):
                skipped += 1
                continue
            contributors.append(
                {
                    "process_name": process_name,
                    "process_id": process_id,
                    "cpu_percent": round(cpu_percent, 1),
                }
            )
        contributors.sort(
            key=lambda item: (
                -_numeric_value(item.get("cpu_percent")),
                _integer_value(item.get("process_id")),
            )
        )
        return _attribution(
            "cpu",
            contributors[: _validated_limit(limit)],
            len(sampled),
            skipped,
            truncated,
            started,
        )
    except Exception:  # Process enumeration is evidence-only and must never break a diagnostic.
        return _unavailable_attribution("cpu", len(sampled), skipped, started)


def collect_memory_process_attribution(
    *,
    limit: int = MAX_CONTRIBUTORS,
    max_processes: int = MAX_PROCESSES_SCANNED,
    time_budget: float = COLLECTION_BUDGET_SECONDS,
) -> ProcessAttribution:
    """Return a bounded snapshot of processes using the most resident memory."""
    started = perf_counter()
    deadline = started + max(0.0, time_budget)
    contributors: list[dict[str, object]] = []
    sampled = 0
    skipped = 0
    truncated = False
    try:
        total_memory = max(0, int(psutil.virtual_memory().total))
        for process in psutil.process_iter(attrs=("pid", "name", "memory_info")):
            if sampled >= max_processes or perf_counter() >= deadline:
                truncated = True
                break
            try:
                process_id = _process_id(process.info.get("pid"))
                if process_id is None or process_id == os.getpid():
                    continue
                memory_info = process.info.get("memory_info")
                if memory_info is None:
                    skipped += 1
                    continue
                resident_bytes = max(0, int(memory_info.rss))
                sampled += 1
                contributors.append(
                    {
                        "process_name": _process_name(process.info.get("name")),
                        "process_id": process_id,
                        "memory_bytes": resident_bytes,
                        "memory_percent": round(
                            (
                                min(100.0, resident_bytes / total_memory * 100)
                                if total_memory
                                else 0.0
                            ),
                            1,
                        ),
                    }
                )
            except (AttributeError, TypeError, ValueError):
                skipped += 1
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                skipped += 1
        contributors.sort(
            key=lambda item: (
                -_integer_value(item.get("memory_bytes")),
                _integer_value(item.get("process_id")),
            )
        )
        return _attribution(
            "memory",
            contributors[: _validated_limit(limit)],
            sampled,
            skipped,
            truncated,
            started,
        )
    except Exception:  # Process enumeration is evidence-only and must never break a diagnostic.
        return _unavailable_attribution("memory", sampled, skipped, started)


def attach_process_attribution(result: CheckResult, attribution: ProcessAttribution) -> CheckResult:
    """Attach non-scoring process evidence while preserving the diagnostic outcome."""
    findings = list(result.findings)
    state = attribution.get("state")
    if state == "partial":
        findings.append(
            "Process attribution is partial because a process was inaccessible or a collection "
            "limit was reached."
        )
    elif state == "unavailable":
        findings.append(
            "Process attribution could not be collected; the pressure result is unchanged."
        )
    return replace(
        result,
        metrics={**result.metrics, "process_attribution": attribution},
        findings=tuple(findings),
    )


def _attribution(
    resource: str,
    contributors: list[dict[str, object]],
    sampled: int,
    skipped: int,
    truncated: bool,
    started: float,
) -> ProcessAttribution:
    state = "partial" if skipped or truncated else "complete"
    return {
        "resource": resource,
        "state": state,
        "contributors": contributors,
        "sampled_processes": sampled,
        "skipped_processes": skipped,
        "truncated": truncated,
        "duration_ms": round(max(0.0, (perf_counter() - started) * 1000), 1),
    }


def _unavailable_attribution(
    resource: str, sampled: int, skipped: int, started: float
) -> ProcessAttribution:
    return {
        "resource": resource,
        "state": "unavailable",
        "contributors": [],
        "sampled_processes": sampled,
        "skipped_processes": skipped,
        "truncated": False,
        "duration_ms": round(max(0.0, (perf_counter() - started) * 1000), 1),
    }


def _validated_limit(limit: int) -> int:
    return min(MAX_CONTRIBUTORS, max(0, limit))


def _process_id(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _process_name(value: object) -> str:
    name = value.strip() if isinstance(value, str) else ""
    return (name or "Unavailable")[:MAX_PROCESS_NAME_LENGTH]


def _numeric_value(value: object) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _integer_value(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
