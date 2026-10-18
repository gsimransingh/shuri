from __future__ import annotations

from threading import Barrier, Event
from time import monotonic, sleep

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


def _hang(release: Event) -> CheckResult:
    release.wait(10)
    return CheckResult("hung", "Hung", CheckStatus.PASS, "Finished far too late")


def test_runner_abandons_a_check_that_exceeds_its_timeout() -> None:
    release = Event()
    registry = DiagnosticRegistry()
    registry.register("hung", lambda: _hang(release))
    registry.register("quick", lambda: CheckResult("quick", "Quick", CheckStatus.PASS, "ok"))

    started = monotonic()
    results = DiagnosticRunner(registry, check_timeout=0.3).run(max_workers=2)
    elapsed = monotonic() - started
    release.set()

    assert elapsed < 3
    assert tuple(result.name for result in results) == ("hung", "quick")
    assert results[0].status is CheckStatus.UNKNOWN
    assert results[0].error == "TimeoutError"
    assert results[1].status is CheckStatus.PASS


def test_runner_enforces_the_overall_scan_deadline_on_unstarted_checks() -> None:
    release = Event()
    registry = DiagnosticRegistry()
    registry.register("hung", lambda: _hang(release))
    registry.register("waiting", lambda: CheckResult("waiting", "W", CheckStatus.PASS, "ok"))

    results = DiagnosticRunner(registry, check_timeout=30, scan_timeout=0.3).run(max_workers=1)
    release.set()

    assert [result.error for result in results] == ["TimeoutError", "TimeoutError"]
    assert all(result.status is CheckStatus.UNKNOWN for result in results)


def test_runner_ignores_a_result_that_arrives_after_its_timeout() -> None:
    release = Event()
    registry = DiagnosticRegistry()
    registry.register("late", lambda: _hang(release))
    events: list[tuple[str, bool]] = []

    results = DiagnosticRunner(registry, check_timeout=0.2).run(
        progress=lambda name, result, _index, _total: events.append((name, result is not None))
    )
    release.set()
    sleep(0.3)

    assert results[0].error == "TimeoutError"
    assert events == [("late", False), ("late", True)]


def test_runner_records_the_error_class_but_not_the_message() -> None:
    registry = DiagnosticRegistry()

    def fail() -> CheckResult:
        raise PermissionError(r"C:\Users\private\secret.txt")

    registry.register("unsafe", fail)
    runner = DiagnosticRunner(registry)

    result = runner.run()[0]

    assert result.error == "PermissionError"
    assert "private" not in str(result)
    assert runner.tracebacks == {}


def test_runner_captures_tracebacks_only_when_asked() -> None:
    registry = DiagnosticRegistry()

    def fail() -> CheckResult:
        raise RuntimeError("boom")

    registry.register("unsafe", fail)
    runner = DiagnosticRunner(registry, capture_tracebacks=True)

    runner.run()

    assert "RuntimeError: boom" in runner.tracebacks["unsafe"]


def test_unknown_diagnostic_names_become_unknown_results() -> None:
    result = DiagnosticRunner(DiagnosticRegistry()).run(("missing",))[0]

    assert result.status is CheckStatus.UNKNOWN
    assert result.error == "UnknownDiagnosticError"
