from __future__ import annotations

import pytest

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
