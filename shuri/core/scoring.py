"""Transparent health-score calculation."""

from __future__ import annotations

from shuri.models import CheckResult, HealthAssessment, ScoreDeduction


def score_label(score: int) -> str:
    """Return the user-facing classification for a score from 0 to 100."""
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Healthy"
    if score >= 60:
        return "Needs Attention"
    if score >= 40:
        return "Poor"
    return "Critical"


def assess_health(results: tuple[CheckResult, ...]) -> HealthAssessment:
    """Calculate score from explicit deductions supplied by diagnostics."""
    deductions: tuple[ScoreDeduction, ...] = tuple(
        deduction for result in results for deduction in result.deductions
    )
    total = sum(max(0, deduction.points) for deduction in deductions)
    score = max(0, min(100, 100 - total))
    return HealthAssessment(score=score, label=score_label(score), deductions=deductions)
