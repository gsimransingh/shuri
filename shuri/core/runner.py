"""Fault-tolerant execution of independent diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from time import perf_counter
from typing import cast

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
        max_workers: int = 1,
        serial_names: tuple[str, ...] = (),
    ) -> tuple[CheckResult, ...]:
        """Run selected diagnostics, or every registered diagnostic in order."""
        selected = names or self._registry.names()
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1.")
        if max_workers > 1 and len(selected) > 1:
            return self._run_concurrently(selected, progress, max_workers, serial_names)
        results: list[CheckResult] = []
        for index, name in enumerate(selected, start=1):
            if progress:
                progress(name, None, index, len(selected))
            result = self._run_one(name)
            results.append(result)
            if progress:
                progress(name, result, index, len(selected))
        return tuple(results)

    def _run_concurrently(
        self,
        selected: tuple[str, ...],
        progress: ProgressCallback | None,
        max_workers: int,
        serial_names: tuple[str, ...],
    ) -> tuple[CheckResult, ...]:
        results: list[CheckResult | None] = [None] * len(selected)
        serial = set(serial_names)
        completed = 0
        for index, name in enumerate(selected):
            if name not in serial:
                continue
            if progress:
                progress(name, None, index + 1, len(selected))
            result = self._run_one(name)
            results[index] = result
            completed += 1
            if progress:
                progress(name, result, completed, len(selected))
        concurrent = tuple(
            (index, name) for index, name in enumerate(selected) if name not in serial
        )
        if not concurrent:
            return cast(tuple[CheckResult, ...], tuple(results))
        with ThreadPoolExecutor(
            max_workers=min(max_workers, len(concurrent)), thread_name_prefix="shuri-check"
        ) as executor:
            futures = {}
            for index, name in concurrent:
                if progress:
                    progress(name, None, index + 1, len(selected))
                futures[executor.submit(self._run_one, name)] = (index, name)
            for completion_index, future in enumerate(as_completed(futures), start=completed + 1):
                index, name = futures[future]
                result = future.result()
                results[index] = result
                if progress:
                    progress(name, result, completion_index, len(selected))
        return cast(tuple[CheckResult, ...], tuple(results))

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
