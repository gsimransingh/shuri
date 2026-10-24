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
    """Calculate score from explicit deductions supplied by diagnostics.

    Coverage and the "Incomplete" label are measured over the checks that *apply* to this machine.
    A ``NOT_APPLICABLE`` check (a Windows-only check on Linux, battery health on a desktop) is not a
    gap, so it never lowers coverage or makes the assessment incomplete. Only a genuine ``UNKNOWN``
    — a check that should work here but could not get evidence — does.
    """
    deductions: tuple[ScoreDeduction, ...] = tuple(
        deduction for result in results for deduction in result.deductions
    )
    total = sum(max(0, deduction.points) for deduction in deductions)
    score = max(0, min(100, 100 - total))
    not_applicable_checks = tuple(
        result.name for result in results if result.status is CheckStatus.NOT_APPLICABLE
    )
    unknown_checks = tuple(
        result.name for result in results if result.status is CheckStatus.UNKNOWN
    )
    applicable = len(results) - len(not_applicable_checks)
    completed_checks = applicable - len(unknown_checks)
    coverage_percent = round(completed_checks / applicable * 100, 1) if applicable else 0.0
    label = score_label(score) if applicable and not unknown_checks else "Incomplete"
    return HealthAssessment(
        score=score,
        label=label,
        deductions=deductions,
        completed_checks=completed_checks,
        unknown_checks=unknown_checks,
        not_applicable_checks=not_applicable_checks,
        coverage_percent=coverage_percent,
        policy_version=SCORING_POLICY_VERSION,
    )
