from __future__ import annotations

from threading import Barrier

import pytest

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


def test_runner_executes_concurrently_but_preserves_registry_order() -> None:
    registry = DiagnosticRegistry()
    barrier = Barrier(2, timeout=2)

    def complete(name: str) -> CheckResult:
        barrier.wait()
        return CheckResult(name, name.title(), CheckStatus.PASS, "Healthy")

    registry.register("first", lambda: complete("first"))
    registry.register("second", lambda: complete("second"))

    results = DiagnosticRunner(registry).run(max_workers=2)

    assert tuple(result.name for result in results) == ("first", "second")


def test_runner_rejects_invalid_worker_count() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        DiagnosticRunner(DiagnosticRegistry()).run(max_workers=0)


def test_runner_completes_serial_checks_before_concurrent_checks() -> None:
    registry = DiagnosticRegistry()
    cpu_finished = False

    def cpu() -> CheckResult:
        nonlocal cpu_finished
        cpu_finished = True
        return CheckResult("cpu", "CPU", CheckStatus.PASS, "Healthy")

    def after_cpu(name: str) -> CheckResult:
        assert cpu_finished
        return CheckResult(name, name.title(), CheckStatus.PASS, "Healthy")

    registry.register("network", lambda: after_cpu("network"))
    registry.register("cpu", cpu)
    registry.register("updates", lambda: after_cpu("updates"))

    results = DiagnosticRunner(registry).run(max_workers=2, serial_names=("cpu",))

    assert tuple(result.name for result in results) == ("network", "cpu", "updates")
