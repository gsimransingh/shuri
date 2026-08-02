"""Storage for the latest locally generated report."""

from __future__ import annotations

import json
import os
import platform
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shuri.core.exceptions import ReportStorageError
from shuri.models import CheckResult, CheckStatus, HealthAssessment, Report, ScoreDeduction
from shuri.utils.constants import MAX_HISTORY_REPORTS, MAX_SAVED_REPORT_BYTES
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


def report_history_path() -> Path:
    """Return the directory containing retained local report history."""
    return latest_report_path().parent / "history"


def save_latest_report(report: Report) -> Path:
    """Persist the latest report and a retained historical copy atomically."""
    path = latest_report_path()
    try:
        _write_report(path, report)
        if report.assessment is not None:
            history_directory = report_history_path()
            generated = report.generated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            _write_report(history_directory / f"{generated}.json", report)
            _prune_report_history(history_directory)
    except OSError as error:
        raise ReportStorageError(
            "The report could not be saved in the user data directory. "
            "Check available space and folder permissions."
        ) from error
    return path


def _write_report(path: Path, report: Report) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent
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


def _prune_report_history(directory: Path, retain: int = MAX_HISTORY_REPORTS) -> None:
    reports = sorted(directory.glob("*.json"), reverse=True)
    for expired in reports[retain:]:
        expired.unlink()


def load_report_history(
    *, limit: int | None = None, assessed_only: bool = False
) -> tuple[Report, ...]:
    """Load retained reports newest first, ignoring damaged history entries."""
    if limit is not None and limit < 1:
        raise ValueError("History limit must be at least 1.")
    directory = report_history_path()
    if not directory.is_dir():
        return ()
    reports: list[Report] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        try:
            if path.stat().st_size > MAX_SAVED_REPORT_BYTES:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            report = report_from_dict(data)
        except (OSError, ValueError, KeyError, TypeError, ReportStorageError):
            continue
        if assessed_only and report.assessment is None:
            continue
        reports.append(report)
        if limit is not None and len(reports) >= limit:
            break
    return tuple(reports)


def clear_report_history() -> int:
    """Delete retained historical reports and return the number removed."""
    directory = report_history_path()
    if not directory.is_dir():
        return 0
    removed = 0
    try:
        for path in directory.glob("*.json"):
            path.unlink()
            removed += 1
    except OSError as error:
        raise ReportStorageError(
            "Report history could not be cleared. Check folder permissions and try again."
        ) from error
    # Synced and managed folders may retain an empty directory temporarily.
    with suppress(OSError):
        directory.rmdir()
    return removed


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
        if path.stat().st_size > MAX_SAVED_REPORT_BYTES:
            raise ReportStorageError(
                "The saved report is too large to load safely. Run 'shuri doctor' again."
            )
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
    if schema_version not in {0, 1, 2, REPORT_SCHEMA_VERSION}:
        raise ReportStorageError(
            f"Report schema {schema_version} is not supported by this Shuri version."
        )
    if not isinstance(data.get("results"), (list, tuple)):
        raise ReportStorageError("Saved report has an invalid results collection.")
    results = tuple(_result_from_dict(item) for item in data["results"])
    assessment_data = data.get("assessment")
    if assessment_data is not None and not isinstance(assessment_data, dict):
        raise ReportStorageError("Saved report has an invalid assessment.")
    if schema_version == 0 and assessment_data:
        assessment_data = dict(assessment_data)
        unknown_checks = tuple(
            result.name for result in results if result.status is CheckStatus.UNKNOWN
        )
        completed_checks = len(results) - len(unknown_checks)
        assessment_data.setdefault("completed_checks", completed_checks)
        assessment_data.setdefault("unknown_checks", list(unknown_checks))
        assessment_data.setdefault(
            "coverage_percent",
            round(completed_checks / len(results) * 100, 1) if results else 0.0,
        )
    assessment = _assessment_from_dict(assessment_data) if assessment_data is not None else None
    try:
        generated_at = datetime.fromisoformat(_string(data.get("generated_at"), "generated_at"))
    except ValueError as error:
        raise ReportStorageError("Saved report has an invalid generated_at.") from error
    legacy_duration = round(sum(result.duration_ms for result in results), 1)
    scan_duration_ms = _number(data.get("scan_duration_ms", legacy_duration), "scan_duration_ms")
    if scan_duration_ms < 0:
        raise ReportStorageError("Saved report has a negative scan_duration_ms.")
    report = Report(
        generated_at=generated_at,
        hostname=_string(data.get("hostname"), "hostname"),
        results=results,
        assessment=assessment,
        shuri_version=_string(data.get("shuri_version", "0.1.0"), "shuri_version"),
        schema_version=REPORT_SCHEMA_VERSION,
        redacted=_boolean(data.get("redacted", False), "redacted"),
        scan_duration_ms=scan_duration_ms,
    )
    if assessment is not None:
        actual_unknown_checks = tuple(
            result.name for result in results if result.status is CheckStatus.UNKNOWN
        )
        if (
            assessment.completed_checks != len(results) - len(actual_unknown_checks)
            or assessment.unknown_checks != actual_unknown_checks
        ):
            raise ReportStorageError("Saved report has inconsistent assessment coverage.")
        expected_coverage = (
            round(assessment.completed_checks / len(results) * 100, 1) if results else 0.0
        )
        if assessment.coverage_percent != expected_coverage:
            raise ReportStorageError("Saved report has inconsistent coverage_percent.")
    return report


def _deduction_from_dict(data: dict[str, Any]) -> ScoreDeduction:
    if not isinstance(data, dict):
        raise ReportStorageError("Saved report contains an invalid score deduction.")
    points = _integer(data.get("points"), "deduction points")
    if points < 0:
        raise ReportStorageError("Saved report has negative deduction points.")
    return ScoreDeduction(
        reason=_string(data.get("reason"), "deduction reason"),
        points=points,
        check=_string(data.get("check"), "deduction check"),
    )


def _result_from_dict(data: dict[str, Any]) -> CheckResult:
    if not isinstance(data, dict):
        raise ReportStorageError("Saved report contains an invalid diagnostic result.")
    metrics = data.get("metrics", {})
    findings = data.get("findings", [])
    deductions = data.get("deductions", [])
    if not isinstance(metrics, dict):
        raise ReportStorageError("Saved report contains invalid diagnostic metrics.")
    if not isinstance(findings, (list, tuple)):
        raise ReportStorageError("Saved report contains invalid diagnostic findings.")
    if not isinstance(deductions, (list, tuple)):
        raise ReportStorageError("Saved report contains invalid diagnostic deductions.")
    duration_ms = _number(data.get("duration_ms", 0), "duration_ms")
    if duration_ms < 0:
        raise ReportStorageError("Saved report has a negative diagnostic duration.")
    try:
        status = CheckStatus(_string(data.get("status"), "diagnostic status"))
    except ValueError as error:
        raise ReportStorageError("Saved report has an invalid diagnostic status.") from error
    return CheckResult(
        name=_string(data.get("name"), "diagnostic name"),
        title=_string(data.get("title"), "diagnostic title"),
        status=status,
        summary=_string(data.get("summary"), "diagnostic summary"),
        metrics=dict(metrics),
        findings=tuple(_string(item, "diagnostic finding") for item in findings),
        deductions=tuple(_deduction_from_dict(item) for item in deductions),
        duration_ms=duration_ms,
    )


def _assessment_from_dict(data: dict[str, Any]) -> HealthAssessment:
    unknown_data = data.get("unknown_checks", [])
    deduction_data = data.get("deductions", [])
    if not isinstance(unknown_data, (list, tuple)):
        raise ReportStorageError("Saved report has invalid unknown_checks.")
    if not isinstance(deduction_data, (list, tuple)):
        raise ReportStorageError("Saved report has invalid assessment deductions.")
    unknown_checks = tuple(_string(item, "unknown check") for item in unknown_data)
    score = _integer(data.get("score"), "score")
    coverage_percent = _number(data.get("coverage_percent", 100.0), "coverage_percent")
    if not 0 <= score <= 100 or not 0 <= coverage_percent <= 100:
        raise ReportStorageError("Saved report has an out-of-range assessment value.")
    completed_checks = _integer(data.get("completed_checks", 0), "completed_checks")
    policy_version = _integer(data.get("policy_version", SCORING_POLICY_VERSION), "policy_version")
    if completed_checks < 0 or policy_version < 1:
        raise ReportStorageError("Saved report has an out-of-range assessment value.")
    assessment = HealthAssessment(
        score=score,
        label=_string(data.get("label"), "assessment label"),
        deductions=tuple(_deduction_from_dict(item) for item in deduction_data),
        completed_checks=completed_checks,
        unknown_checks=unknown_checks,
        coverage_percent=coverage_percent,
        policy_version=policy_version,
    )
    if assessment.score != max(0, 100 - assessment.total_deductions):
        raise ReportStorageError("Saved report has an inconsistent assessment score.")
    return assessment


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReportStorageError(f"Saved report has an invalid {field_name}.")
    return value


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ReportStorageError(f"Saved report has an invalid {field_name}.")
    return value


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ReportStorageError(f"Saved report has an invalid {field_name}.")
    return value


def _number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReportStorageError(f"Saved report has an invalid {field_name}.")
    return float(value)
