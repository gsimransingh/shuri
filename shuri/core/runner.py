"""Fault-tolerant execution of independent diagnostics."""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter

from shuri.core.registry import DiagnosticRegistry
from shuri.models import CheckResult, CheckStatus


class DiagnosticRunner:
    """Run diagnostics without allowing one collection failure to stop a scan."""

    def __init__(self, registry: DiagnosticRegistry) -> None:
        self._registry = registry

    def run(self, names: tuple[str, ...] | None = None) -> tuple[CheckResult, ...]:
        """Run selected diagnostics, or every registered diagnostic in order."""
        selected = names or self._registry.names()
        return tuple(self._run_one(name) for name in selected)

    def _run_one(self, name: str) -> CheckResult:
        start = perf_counter()
        try:
            result = self._registry.get(name)()
        except Exception as error:  # Diagnostics must not make the CLI unusable.
            result = CheckResult(
                name=name,
                title=name.replace("_", " ").title(),
                status=CheckStatus.UNKNOWN,
                summary="Diagnostic could not be completed.",
                findings=(f"{type(error).__name__}: {error}",),
            )
        duration_ms = (perf_counter() - start) * 1000
        return replace(result, duration_ms=round(duration_ms, 1))
