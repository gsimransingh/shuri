"""Storage for the latest locally generated report."""

from __future__ import annotations

import json
import os
import platform
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from shuri.core.exceptions import ReportStorageError
from shuri.models import CheckResult, CheckStatus, HealthAssessment, Report, ScoreDeduction
from shuri.version import REPORT_SCHEMA_VERSION, SCORING_POLICY_VERSION


def latest_report_path() -> Path:
    """Return the platform-appropriate per-user report-state path."""
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "shuri" / "latest-report.json"


def legacy_report_path() -> Path:
    """Return the pre-0.3 report path used in the current working directory."""
    return Path.cwd() / ".shuri" / "latest-report.json"


def save_latest_report(report: Report) -> Path:
    """Persist a JSON copy atomically for the ``report`` command."""
    path = latest_report_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".latest-report-", suffix=".tmp", dir=path.parent
        )
        temporary_path = Path(temporary_name)
        try:
            try:
                handle = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
            except Exception:
                os.close(descriptor)
                raise
            with handle:
                json.dump(report.to_dict(), handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
    except OSError as error:
        raise ReportStorageError(
            "The latest report could not be saved in the user data directory. "
            "Check available space and folder permissions."
        ) from error
    return path


def load_latest_report() -> Report | None:
    """Load the most recent report, returning ``None`` when unavailable."""
    path = latest_report_path()
    legacy_path = legacy_report_path()
    migrate = not path.is_file() and legacy_path.is_file() and legacy_path != path
    if migrate:
        path = legacy_path
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ReportStorageError("Saved report must contain a JSON object.")
        report = report_from_dict(data)
        if migrate:
            save_latest_report(report)
        return report
    except ReportStorageError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ReportStorageError(
            "The saved report is corrupt or cannot be read. Run 'shuri doctor' again."
        ) from error


def report_from_dict(data: dict[str, Any]) -> Report:
    """Rehydrate a report previously produced by :meth:`Report.to_dict`."""
    schema_version = _integer(data.get("schema_version", 0), "schema_version")
    if schema_version not in {0, 1, REPORT_SCHEMA_VERSION}:
        raise ReportStorageError(
            f"Report schema {schema_version} is not supported by this Shuri version."
        )
    if not isinstance(data.get("results"), (list, tuple)):
        raise ReportStorageError("Saved report has an invalid results collection.")
    results = tuple(_result_from_dict(item) for item in data["results"])
    assessment_data = data.get("assessment")
    if assessment_data is not None and not isinstance(assessment_data, dict):
        raise ReportStorageError("Saved report has an invalid assessment.")
    assessment = _assessment_from_dict(assessment_data) if assessment_data else None
    return Report(
        generated_at=datetime.fromisoformat(data["generated_at"]),
        hostname=str(data["hostname"]),
        results=results,
        assessment=assessment,
        shuri_version=str(data.get("shuri_version", "0.1.0")),
        schema_version=REPORT_SCHEMA_VERSION,
        redacted=_boolean(data.get("redacted", False), "redacted"),
    )


def _deduction_from_dict(data: dict[str, Any]) -> ScoreDeduction:
    return ScoreDeduction(
        reason=str(data["reason"]), points=int(data["points"]), check=str(data["check"])
    )


def _result_from_dict(data: dict[str, Any]) -> CheckResult:
    if not isinstance(data, dict):
        raise ReportStorageError("Saved report contains an invalid diagnostic result.")
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
    unknown_checks = tuple(str(item) for item in data.get("unknown_checks", []))
    return HealthAssessment(
        score=int(data["score"]),
        label=str(data["label"]),
        deductions=tuple(_deduction_from_dict(item) for item in data.get("deductions", [])),
        completed_checks=_integer(data.get("completed_checks", 0), "completed_checks"),
        unknown_checks=unknown_checks,
        coverage_percent=float(data.get("coverage_percent", 100.0)),
        policy_version=_integer(
            data.get("policy_version", SCORING_POLICY_VERSION), "policy_version"
        ),
    )


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReportStorageError(f"Saved report has an invalid {field_name}.")
    return value


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ReportStorageError(f"Saved report has an invalid {field_name}.")
    return value
