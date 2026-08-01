"""Fault-tolerant execution of independent diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from time import perf_counter

from shuri.core.registry import DiagnosticRegistry
from shuri.models import CheckResult, CheckStatus

type ProgressCallback = Callable[[str, CheckResult | None, int, int], None]


class DiagnosticRunner:
    """Run diagnostics without allowing one collection failure to stop a scan."""

    def __init__(self, registry: DiagnosticRegistry) -> None:
        self._registry = registry

    def run(
        self,
        names: tuple[str, ...] | None = None,
        progress: ProgressCallback | None = None,
    ) -> tuple[CheckResult, ...]:
        """Run selected diagnostics, or every registered diagnostic in order."""
        selected = names or self._registry.names()
        results: list[CheckResult] = []
        for index, name in enumerate(selected, start=1):
            if progress:
                progress(name, None, index, len(selected))
            result = self._run_one(name)
            results.append(result)
            if progress:
                progress(name, result, index, len(selected))
        return tuple(results)

    def _run_one(self, name: str) -> CheckResult:
        start = perf_counter()
        try:
            result = self._registry.get(name)()
        except Exception:  # Diagnostics must not make the CLI unusable.
            result = CheckResult(
                name=name,
                title=name.replace("_", " ").title(),
                status=CheckStatus.UNKNOWN,
                summary="Diagnostic could not be completed.",
                findings=(
                    "The diagnostic failed unexpectedly; retry and report it if it persists.",
                ),
            )
        duration_ms = (perf_counter() - start) * 1000
        return replace(result, duration_ms=round(duration_ms, 1))
