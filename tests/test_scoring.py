from __future__ import annotations

import pytest

from shuri.core.scoring import assess_health, score_label
from shuri.models import CheckResult, CheckStatus, ScoreDeduction


def test_assessment_collects_explicit_deductions() -> None:
    result = CheckResult(
        name="disk",
        title="Disk",
        status=CheckStatus.FAIL,
        summary="Low space",
        deductions=(ScoreDeduction("System drive is below 10% free", 15, "disk"),),
    )

    assessment = assess_health((result,))

    assert assessment.score == 85
    assert assessment.label == "Healthy"
    assert assessment.deductions == result.deductions
    assert assessment.total_deductions == 15


def test_assessment_never_falls_below_zero() -> None:
    result = CheckResult(
        name="test",
        title="Test",
        status=CheckStatus.FAIL,
        summary="Bad",
        deductions=(ScoreDeduction("Large deduction", 150, "test"),),
    )

    assert assess_health((result,)).score == 0


def test_score_labels_match_published_boundaries() -> None:
    assert score_label(90) == "Excellent"
    assert score_label(75) == "Healthy"
    assert score_label(60) == "Needs Attention"
    assert score_label(40) == "Poor"
    assert score_label(39) == "Critical"


def test_unknown_checks_make_assessment_explicitly_incomplete() -> None:
    results = (
        CheckResult("cpu", "CPU", CheckStatus.PASS, "Normal"),
        CheckResult("updates", "Updates", CheckStatus.UNKNOWN, "Unavailable"),
    )

    assessment = assess_health(results)

    assert assessment.score == 100
    assert assessment.label == "Incomplete"
    assert assessment.completed_checks == 1
    assert assessment.unknown_checks == ("updates",)
    assert assessment.coverage_percent == 50.0


def test_empty_assessment_has_zero_coverage() -> None:
    assessment = assess_health(())

    assert assessment.coverage_percent == 0.0
    assert assessment.completed_checks == 0
    assert assessment.label == "Incomplete"


def test_negative_deductions_are_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        ScoreDeduction("Invalid", -1, "test")
