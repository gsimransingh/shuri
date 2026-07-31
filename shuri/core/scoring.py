"""Transparent health-score calculation."""

from __future__ import annotations

from shuri.models import CheckResult, CheckStatus, HealthAssessment, ScoreDeduction
from shuri.version import SCORING_POLICY_VERSION


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
    unknown_checks = tuple(
        result.name for result in results if result.status is CheckStatus.UNKNOWN
    )
    completed_checks = len(results) - len(unknown_checks)
    coverage_percent = round(completed_checks / len(results) * 100, 1) if results else 0.0
    label = score_label(score) if results and not unknown_checks else "Incomplete"
    return HealthAssessment(
        score=score,
        label=label,
        deductions=deductions,
        completed_checks=completed_checks,
        unknown_checks=unknown_checks,
        coverage_percent=coverage_percent,
        policy_version=SCORING_POLICY_VERSION,
    )
