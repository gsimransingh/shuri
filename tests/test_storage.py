from __future__ import annotations

import json
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
