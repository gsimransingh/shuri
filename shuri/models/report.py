"""Structured, serialisable data exchanged between Shuri components."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


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


@dataclass(frozen=True, slots=True)
class Report:
    """Complete workstation assessment ready for rendering or export."""

    generated_at: datetime
    hostname: str
    results: tuple[CheckResult, ...]
    assessment: HealthAssessment | None = None
    shuri_version: str = "0.1.0"

    @classmethod
    def create(
        cls,
        results: tuple[CheckResult, ...],
        hostname: str,
        assessment: HealthAssessment | None = None,
    ) -> Report:
        """Create a report with a timezone-aware timestamp."""
        return cls(
            generated_at=datetime.now(UTC),
            hostname=hostname,
            results=results,
            assessment=assessment,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report data."""
        data = asdict(self)
        data["generated_at"] = self.generated_at.isoformat()
        return data
