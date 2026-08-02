"""Execution and scoring services for Shuri."""

from __future__ import annotations

from shuri.core.comparison import MetricChange, ReportComparison, StatusChange, compare_reports
from shuri.core.registry import DiagnosticRegistry, default_registry
from shuri.core.runner import DiagnosticRunner
from shuri.core.scoring import assess_health

__all__ = [
    "DiagnosticRegistry",
    "DiagnosticRunner",
    "MetricChange",
    "ReportComparison",
    "StatusChange",
    "assess_health",
    "compare_reports",
    "default_registry",
]
