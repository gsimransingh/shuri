"""Structured, serialisable data exchanged between Shuri components."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from shuri.version import REPORT_SCHEMA_VERSION, SCORING_POLICY_VERSION, __version__


class CheckStatus(StrEnum):
    """Outcome of one diagnostic."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ScoreDeduction:
    """An explainable score adjustment made by a diagnostic."""

    reason: str
    points: int
    check: str

    def __post_init__(self) -> None:
        if self.points < 0:
            raise ValueError("Score deductions cannot have negative points.")


@dataclass(frozen=True, slots=True)
class CheckResult:
    """A self-contained diagnostic result."""

    name: str
    title: str
    status: CheckStatus
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    findings: tuple[str, ...] = ()
    deductions: tuple[ScoreDeduction, ...] = ()
    duration_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class HealthAssessment:
    """Overall score calculated from individual results."""

    score: int
    label: str
    deductions: tuple[ScoreDeduction, ...] = ()
    completed_checks: int = 0
    unknown_checks: tuple[str, ...] = ()
    coverage_percent: float = 100.0
    policy_version: int = SCORING_POLICY_VERSION

    @property
    def total_deductions(self) -> int:
        """Return the total points removed from the starting health score."""
        return sum(max(0, deduction.points) for deduction in self.deductions)


@dataclass(frozen=True, slots=True)
class Report:
    """Complete workstation assessment ready for rendering or export."""

    generated_at: datetime
    hostname: str
    results: tuple[CheckResult, ...]
    assessment: HealthAssessment | None = None
    shuri_version: str = __version__
    schema_version: int = REPORT_SCHEMA_VERSION
    redacted: bool = False
    scan_duration_ms: float = 0.0

    @property
    def duration_ms(self) -> float:
        """Return wall-clock scan time, or cumulative time for legacy reports."""
        if self.scan_duration_ms > 0:
            return round(self.scan_duration_ms, 1)
        return round(sum(result.duration_ms for result in self.results), 1)

    @classmethod
    def create(
        cls,
        results: tuple[CheckResult, ...],
        hostname: str,
        assessment: HealthAssessment | None = None,
        scan_duration_ms: float = 0.0,
    ) -> Report:
        """Create a report with a timezone-aware timestamp."""
        return cls(
            generated_at=datetime.now(UTC),
            hostname=hostname,
            results=results,
            assessment=assessment,
            scan_duration_ms=scan_duration_ms,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report data."""
        data = asdict(self)
        data["generated_at"] = self.generated_at.isoformat()
        if self.assessment is not None:
            data["assessment"]["total_deductions"] = self.assessment.total_deductions
        return data
