from __future__ import annotations

from shuri.core.registry import DiagnosticRegistry
from shuri.core.runner import DiagnosticRunner
from shuri.models import CheckResult, CheckStatus


def test_runner_reports_progress_and_duration() -> None:
    registry = DiagnosticRegistry()
    registry.register("cpu", lambda: CheckResult("cpu", "CPU", CheckStatus.PASS, "Healthy"))
    events: list[tuple[str, bool, int, int]] = []

    results = DiagnosticRunner(registry).run(
        progress=lambda name, result, index, total: events.append(
            (name, result is not None, index, total)
        )
    )

    assert events == [("cpu", False, 1, 1), ("cpu", True, 1, 1)]
    assert results[0].duration_ms >= 0


def test_runner_isolates_exceptions_without_leaking_details() -> None:
    registry = DiagnosticRegistry()

    def fail() -> CheckResult:
        raise RuntimeError("password=super-secret")

    registry.register("unsafe", fail)

    result = DiagnosticRunner(registry).run()[0]

    assert result.status is CheckStatus.UNKNOWN
    assert "super-secret" not in str(result)
