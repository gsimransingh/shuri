"""Disk-specific data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiskSnapshot:
    """A mounted filesystem and its capacity."""

    device: str
    mountpoint: str
    filesystem: str
    total_bytes: int
    free_bytes: int
    used_percent: float
