"""Comparison of two completed workstation assessments."""

from __future__ import annotations

from dataclasses import dataclass

from shuri.models import CheckStatus, Report

_TRACKED_METRICS = {
    ("cpu", "utilisation_percent"): ("CPU utilisation", "%"),
    ("memory", "available_percent"): ("Memory available", "%"),
    ("memory", "swap_percent"): ("Swap used", "%"),
    ("battery", "battery_health_percent"): ("Battery health", "%"),
    ("battery", "charge_percent"): ("Battery charge", "%"),
    ("system", "system_disk_free_bytes"): ("System disk free", "bytes"),
    ("updates", "available_updates"): ("Available updates", ""),
    ("eventlogs", "critical"): ("Critical events", ""),
    ("eventlogs", "errors"): ("Error events", ""),
    ("eventlogs", "warnings"): ("Warning events", ""),
}


@dataclass(frozen=True, slots=True)
class StatusChange:
    """A diagnostic status transition between two reports."""

    name: str
    title: str
    older: CheckStatus
    newer: CheckStatus


@dataclass(frozen=True, slots=True)
class MetricChange:
    """A changed numeric metric that is useful for workstation trends."""

    label: str
    older: float
    newer: float
    unit: str

    @property
    def delta(self) -> float:
        return self.newer - self.older


@dataclass(frozen=True, slots=True)
class ReportComparison:
    """Stable summary of meaningful changes between two assessments."""

    older: Report
    newer: Report
    score_change: int
    coverage_change: float
    status_changes: tuple[StatusChange, ...]
    metric_changes: tuple[MetricChange, ...]
    added_checks: tuple[str, ...]
    removed_checks: tuple[str, ...]


def compare_reports(older: Report, newer: Report) -> ReportComparison:
    """Compare two assessed reports in chronological order."""
    if older.assessment is None or newer.assessment is None:
        raise ValueError("Both reports must contain health assessments.")
    older_results = {result.name: result for result in older.results}
    newer_results = {result.name: result for result in newer.results}
    common = older_results.keys() & newer_results.keys()
    changes = tuple(
        StatusChange(
            name=name,
            title=newer_results[name].title,
            older=older_results[name].status,
            newer=newer_results[name].status,
        )
        for name in newer_results
        if name in common and older_results[name].status is not newer_results[name].status
    )
    metric_changes: list[MetricChange] = []
    for (check, key), (label, unit) in _TRACKED_METRICS.items():
        if check not in common:
            continue
        older_value = older_results[check].metrics.get(key)
        newer_value = newer_results[check].metrics.get(key)
        if (
            isinstance(older_value, (int, float))
            and not isinstance(older_value, bool)
            and isinstance(newer_value, (int, float))
            and not isinstance(newer_value, bool)
            and older_value != newer_value
        ):
            metric_changes.append(MetricChange(label, float(older_value), float(newer_value), unit))
    return ReportComparison(
        older=older,
        newer=newer,
        score_change=newer.assessment.score - older.assessment.score,
        coverage_change=round(
            newer.assessment.coverage_percent - older.assessment.coverage_percent, 1
        ),
        status_changes=changes,
        metric_changes=tuple(metric_changes),
        added_checks=tuple(name for name in newer_results if name not in older_results),
        removed_checks=tuple(name for name in older_results if name not in newer_results),
    )
