"""CPU-specific data models kept available for future check expansion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CpuSnapshot:
    """Collected CPU measurements."""

    model: str
    architecture: str
    physical_cores: int | None
    logical_cores: int | None
    utilisation_percent: float
    frequency_mhz: float | None
