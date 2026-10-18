"""Fault-tolerant, deadline-bounded execution of independent diagnostics."""

from __future__ import annotations

import queue
import threading
import traceback
from collections import deque
from collections.abc import Callable
from dataclasses import replace
from time import monotonic, perf_counter

from shuri.core.registry import DiagnosticRegistry
from shuri.models import CheckResult, CheckStatus

type ProgressCallback = Callable[[str, CheckResult | None, int, int], None]

DEFAULT_CHECK_TIMEOUT_SECONDS = 45.0
DEFAULT_SCAN_TIMEOUT_SECONDS = 90.0
_POLL_SECONDS = 0.1


def _title(name: str) -> str:
    return name.replace("_", " ").title()


class DiagnosticRunner:
    """Run diagnostics without letting one failure or hang stop a scan.

    Each diagnostic runs on its own daemon thread. A diagnostic that raises becomes ``UNKNOWN``,
    and one that exceeds ``check_timeout`` (or the overall ``scan_timeout``) is abandoned and
    reported as ``UNKNOWN``. Python cannot kill a thread, so an abandoned diagnostic may keep
    running in the background, but daemon threads never delay the program from exiting.
    """

    def __init__(
        self,
        registry: DiagnosticRegistry,
        *,
        check_timeout: float = DEFAULT_CHECK_TIMEOUT_SECONDS,
        scan_timeout: float = DEFAULT_SCAN_TIMEOUT_SECONDS,
        capture_tracebacks: bool = False,
    ) -> None:
        self._registry = registry
        self._check_timeout = check_timeout
        self._scan_timeout = scan_timeout
        self._capture_tracebacks = capture_tracebacks
        self.tracebacks: dict[str, str] = {}
        """Formatted tracebacks of failed diagnostics, collected only when requested."""

    def run(
        self,
        names: tuple[str, ...] | None = None,
        progress: ProgressCallback | None = None,
        max_workers: int = 1,
        serial_names: tuple[str, ...] = (),
    ) -> tuple[CheckResult, ...]:
        """Run selected diagnostics, or every registered diagnostic in order."""
        selected = names or self._registry.names()
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1.")
        results: list[CheckResult | None] = [None] * len(selected)
        serial = [index for index, name in enumerate(selected) if name in serial_names]
        concurrent = [index for index, name in enumerate(selected) if name not in serial_names]
        execution = _Execution(
            selected, results, progress, monotonic() + self._scan_timeout, self._check_timeout
        )
        if serial:
            self._execute(execution, serial, 1)
        if concurrent:
            self._execute(execution, concurrent, max_workers)
        return tuple(result for result in results if result is not None)

    def _execute(self, execution: _Execution, indices: list[int], limit: int) -> None:
        pending = deque(indices)
        running: dict[int, float] = {}
        finished: queue.Queue[tuple[int, CheckResult]] = queue.Queue()
        while pending or running:
            now = monotonic()
            while pending and len(running) < limit and now < execution.scan_deadline:
                index = pending.popleft()
                running[index] = now
                execution.starting(index)
                threading.Thread(
                    target=self._work,
                    args=(index, execution.names[index], finished),
                    name=f"shuri-check-{execution.names[index]}",
                    daemon=True,
                ).start()
            try:
                index, result = finished.get(timeout=self._wait_seconds(execution, running))
            except queue.Empty:
                pass
            else:
                if index in running:  # A result that arrives after a timeout is discarded.
                    del running[index]
                    execution.finish(index, result)
            now = monotonic()
            for index, started in tuple(running.items()):
                if now - started >= execution.check_timeout or now >= execution.scan_deadline:
                    del running[index]
                    execution.finish(index, _timeout_result(execution.names[index], started, now))
            if now >= execution.scan_deadline:
                while pending:
                    index = pending.popleft()
                    execution.starting(index)
                    execution.finish(index, _timeout_result(execution.names[index], now, now))

    @staticmethod
    def _wait_seconds(execution: _Execution, running: dict[int, float]) -> float:
        if not running:
            return 0.0
        now = monotonic()
        next_expiry = min(
            min(started + execution.check_timeout for started in running.values()),
            execution.scan_deadline,
        )
        return max(0.0, min(_POLL_SECONDS, next_expiry - now))

    def _work(self, index: int, name: str, finished: queue.Queue[tuple[int, CheckResult]]) -> None:
        finished.put((index, self._run_one(name)))

    def _run_one(self, name: str) -> CheckResult:
        start = perf_counter()
        try:
            result = self._registry.get(name)()
        except Exception as error:  # Diagnostics must not make the CLI unusable.
            kind = type(error).__name__
            if self._capture_tracebacks:
                self.tracebacks[name] = traceback.format_exc()
            result = CheckResult(
                name=name,
                title=_title(name),
                status=CheckStatus.UNKNOWN,
                summary="Diagnostic could not be completed.",
                findings=(
                    f"The diagnostic failed unexpectedly ({kind}). Rerun with 'shuri --debug' "
                    "for details and report it if it persists.",
                ),
                error=kind,
            )
        duration_ms = (perf_counter() - start) * 1000
        return replace(result, duration_ms=round(duration_ms, 1))


class _Execution:
    """Shared bookkeeping for one scan: ordering, progress, and deadlines."""

    def __init__(
        self,
        names: tuple[str, ...],
        results: list[CheckResult | None],
        progress: ProgressCallback | None,
        scan_deadline: float,
        check_timeout: float,
    ) -> None:
        self.names = names
        self.scan_deadline = scan_deadline
        self.check_timeout = check_timeout
        self._results = results
        self._progress = progress
        self._completed = 0

    def starting(self, index: int) -> None:
        if self._progress:
            self._progress(self.names[index], None, index + 1, len(self.names))

    def finish(self, index: int, result: CheckResult) -> None:
        self._results[index] = result
        self._completed += 1
        if self._progress:
            self._progress(self.names[index], result, self._completed, len(self.names))


def _timeout_result(name: str, started: float, now: float) -> CheckResult:
    return CheckResult(
        name=name,
        title=_title(name),
        status=CheckStatus.UNKNOWN,
        summary="Diagnostic did not finish in time.",
        findings=("The diagnostic timed out; try again, or run it on its own.",),
        duration_ms=round(max(0.0, now - started) * 1000, 1),
        error="TimeoutError",
    )
