"""Storage for the latest locally generated report."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from shuri.models import CheckResult, CheckStatus, HealthAssessment, Report, ScoreDeduction


def latest_report_path() -> Path:
    """Return a workspace-local cache location without writing to it."""
    return Path.cwd() / ".shuri" / "latest-report.json"


def save_latest_report(report: Report) -> Path:
    """Persist a JSON copy for the ``report`` command."""
    path = latest_report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path


def load_latest_report() -> Report | None:
    """Load the most recent report, returning ``None`` when unavailable."""
    path = latest_report_path()
    if not path.is_file():
        return None
    return report_from_dict(json.loads(path.read_text(encoding="utf-8")))


def report_from_dict(data: dict[str, Any]) -> Report:
    """Rehydrate a report previously produced by :meth:`Report.to_dict`."""
    results = tuple(_result_from_dict(item) for item in data["results"])
    assessment_data = data.get("assessment")
    assessment = _assessment_from_dict(assessment_data) if assessment_data else None
    return Report(
        generated_at=datetime.fromisoformat(data["generated_at"]),
        hostname=str(data["hostname"]),
        results=results,
        assessment=assessment,
        shuri_version=str(data.get("shuri_version", "0.1.0")),
    )


def _deduction_from_dict(data: dict[str, Any]) -> ScoreDeduction:
    return ScoreDeduction(
        reason=str(data["reason"]), points=int(data["points"]), check=str(data["check"])
    )


def _result_from_dict(data: dict[str, Any]) -> CheckResult:
    return CheckResult(
        name=str(data["name"]),
        title=str(data["title"]),
        status=CheckStatus(data["status"]),
        summary=str(data["summary"]),
        metrics=dict(data.get("metrics", {})),
        findings=tuple(str(item) for item in data.get("findings", [])),
        deductions=tuple(_deduction_from_dict(item) for item in data.get("deductions", [])),
        duration_ms=float(data.get("duration_ms", 0)),
    )


def _assessment_from_dict(data: dict[str, Any]) -> HealthAssessment:
    return HealthAssessment(
        score=int(data["score"]),
        label=str(data["label"]),
        deductions=tuple(_deduction_from_dict(item) for item in data.get("deductions", [])),
    )
