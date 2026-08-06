"""Typed physical-drive inventory and reliability evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PhysicalDriveSnapshot:
    """Read-only health evidence exposed by Windows Storage Management."""

    device_id: str
    model: str
    media_type: str
    bus_type: str
    health_status: str
    operational_status: tuple[str, ...]
    size_bytes: int
    temperature_celsius: float | None = None
    wear_percent: float | None = None
    read_errors_total: int | None = None
    write_errors_total: int | None = None
    power_on_hours: int | None = None
