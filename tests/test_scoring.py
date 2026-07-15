from __future__ import annotations

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
