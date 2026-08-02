from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from shuri.core import storage
from shuri.core.exceptions import ReportStorageError
from shuri.core.scoring import assess_health
from shuri.core.storage import report_from_dict
from shuri.models import CheckResult, CheckStatus, Report
from shuri.version import REPORT_SCHEMA_VERSION


def test_report_round_trip_preserves_schema_and_coverage() -> None:
    results = (CheckResult("cpu", "CPU", CheckStatus.UNKNOWN, "Unavailable"),)
    original = Report.create(results, "workstation-01", assess_health(results))

    restored = report_from_dict(original.to_dict())

    assert restored.schema_version == REPORT_SCHEMA_VERSION
    assert restored.assessment is not None
    assert restored.assessment.label == "Incomplete"
    assert restored.assessment.unknown_checks == ("cpu",)


def test_legacy_report_without_schema_version_is_migrated() -> None:
    restored = report_from_dict(
        {
            "generated_at": "2026-08-01T00:00:00+00:00",
            "hostname": "workstation-01",
            "results": [],
            "assessment": None,
        }
    )

    assert restored.schema_version == REPORT_SCHEMA_VERSION


def test_legacy_assessment_coverage_is_derived() -> None:
    restored = report_from_dict(
        {
            "generated_at": "2026-08-01T00:00:00+00:00",
            "hostname": "workstation-01",
            "results": [
                {
                    "name": "updates",
                    "title": "Updates",
                    "status": "unknown",
                    "summary": "Unavailable",
                }
            ],
            "assessment": {"score": 100, "label": "Incomplete", "deductions": []},
        }
    )

    assert restored.assessment is not None
    assert restored.assessment.completed_checks == 0
    assert restored.assessment.unknown_checks == ("updates",)
    assert restored.assessment.coverage_percent == 0.0


def test_future_report_schema_is_rejected() -> None:
    with pytest.raises(ReportStorageError, match="not supported"):
        report_from_dict({"schema_version": 999, "results": []})


def test_invalid_results_collection_is_rejected() -> None:
    with pytest.raises(ReportStorageError, match="results"):
        report_from_dict({"schema_version": REPORT_SCHEMA_VERSION, "results": {}})


def test_latest_report_is_saved_atomically_to_stable_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state" / "latest-report.json"
    monkeypatch.setattr(storage, "latest_report_path", lambda: target)
    report = Report.create((), "workstation-01")

    saved = storage.save_latest_report(report)

    assert saved == target
    assert storage.load_latest_report() == report
    assert not tuple(target.parent.glob("*.tmp"))


def test_report_history_is_newest_first_and_can_filter_assessments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state" / "latest-report.json"
    monkeypatch.setattr(storage, "latest_report_path", lambda: target)
    first = Report(datetime(2026, 8, 1, tzinfo=UTC), "host", (), assessment=assess_health(()))
    second = Report(datetime(2026, 8, 2, tzinfo=UTC), "host", ())
    third = Report(datetime(2026, 8, 3, tzinfo=UTC), "host", (), assessment=assess_health(()))
    for report in (first, second, third):
        storage.save_latest_report(report)

    assert storage.load_report_history() == (third, first)
    assert storage.load_report_history(assessed_only=True) == (third, first)
    assert storage.load_report_history(limit=1) == (third,)
    assert storage.load_latest_report() == third


def test_history_retention_keeps_the_newest_fifty_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state" / "latest-report.json"
    monkeypatch.setattr(storage, "latest_report_path", lambda: target)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(52):
        storage.save_latest_report(
            Report(
                start + timedelta(days=index),
                "host",
                (),
                assessment=assess_health(()),
            )
        )

    history = storage.load_report_history()

    assert len(history) == 50
    assert history[0].generated_at == start + timedelta(days=51)
    assert history[-1].generated_at == start + timedelta(days=2)


def test_corrupt_history_is_ignored_and_history_can_be_cleared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state" / "latest-report.json"
    monkeypatch.setattr(storage, "latest_report_path", lambda: target)
    report = Report.create((), "host", assess_health(()))
    storage.save_latest_report(report)
    history_directory = storage.report_history_path()
    (history_directory / "broken.json").write_text("{bad-json", encoding="utf-8")

    assert storage.load_report_history() == (report,)
    assert storage.clear_report_history() == 2
    assert storage.load_report_history() == ()
    assert target.is_file()


def test_legacy_report_is_copied_to_stable_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "new" / "latest-report.json"
    legacy = tmp_path / "old" / "latest-report.json"
    report = Report.create((), "workstation-01")
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps(report.to_dict()), encoding="utf-8")
    monkeypatch.setattr(storage, "latest_report_path", lambda: target)
    monkeypatch.setattr(storage, "legacy_report_path", lambda: legacy)

    restored = storage.load_latest_report()

    assert restored == report
    assert target.is_file()


def test_corrupt_saved_report_has_recovery_guidance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "latest-report.json"
    target.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(storage, "latest_report_path", lambda: target)
    monkeypatch.setattr(storage, "legacy_report_path", lambda: tmp_path / "legacy.json")

    with pytest.raises(ReportStorageError, match="Run 'shuri doctor' again"):
        storage.load_latest_report()


def test_oversized_saved_report_is_rejected_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "latest-report.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(storage, "MAX_SAVED_REPORT_BYTES", 1)
    monkeypatch.setattr(storage, "latest_report_path", lambda: target)
    monkeypatch.setattr(storage, "legacy_report_path", lambda: tmp_path / "legacy.json")

    with pytest.raises(ReportStorageError, match="too large"):
        storage.load_latest_report()


def test_nested_report_field_types_are_validated() -> None:
    report = Report.create(
        (CheckResult("cpu", "CPU", CheckStatus.PASS, "Healthy"),), "workstation-01"
    ).to_dict()
    report["results"][0]["findings"] = "not-a-list"

    with pytest.raises(ReportStorageError, match="findings"):
        report_from_dict(report)
