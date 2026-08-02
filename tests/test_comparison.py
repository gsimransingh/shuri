from __future__ import annotations

from datetime import UTC, datetime

import pytest

from shuri.core.comparison import compare_reports
from shuri.core.scoring import assess_health
from shuri.models import CheckResult, CheckStatus, Report, ScoreDeduction


def _assessed_report(generated_at: datetime, results: tuple[CheckResult, ...]) -> Report:
    return Report(
        generated_at=generated_at,
        hostname="workstation-01",
        results=results,
        assessment=assess_health(results),
    )


def test_comparison_reports_score_coverage_and_status_changes() -> None:
    older_result = CheckResult(
        "disk",
        "Disk",
        CheckStatus.FAIL,
        "Disk is critically low.",
        deductions=(ScoreDeduction("Disk is critically low", 15, "disk"),),
    )
    newer_results = (
        CheckResult("disk", "Disk", CheckStatus.PASS, "Disk is healthy."),
        CheckResult("updates", "Updates", CheckStatus.UNKNOWN, "Unavailable"),
        CheckResult(
            "memory",
            "Memory",
            CheckStatus.PASS,
            "Healthy",
            metrics={"available_percent": 40.0},
        ),
    )
    older = _assessed_report(
        datetime(2026, 8, 1, tzinfo=UTC),
        (
            older_result,
            CheckResult(
                "memory",
                "Memory",
                CheckStatus.PASS,
                "Healthy",
                metrics={"available_percent": 25.0},
            ),
        ),
    )
    newer = _assessed_report(datetime(2026, 8, 2, tzinfo=UTC), newer_results)

    comparison = compare_reports(older, newer)

    assert comparison.score_change == 15
    assert comparison.coverage_change == pytest.approx(-33.3)
    assert comparison.status_changes[0].name == "disk"
    assert comparison.status_changes[0].older is CheckStatus.FAIL
    assert comparison.status_changes[0].newer is CheckStatus.PASS
    assert comparison.metric_changes[0].label == "Memory available"
    assert comparison.metric_changes[0].delta == 15.0
    assert comparison.added_checks == ("updates",)
    assert comparison.removed_checks == ()


def test_comparison_requires_assessed_reports() -> None:
    report = Report.create((), "workstation-01")

    with pytest.raises(ValueError, match="health assessments"):
        compare_reports(report, report)
