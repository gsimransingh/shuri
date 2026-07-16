from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SystemInfo:
    """A point-in-time snapshot of workstation system information."""

    hostname: str
    os_name: str
    os_release: str
    os_version: str
    architecture: str
    processor: str
    python_version: str
    physical_cores: int | None
    logical_cores: int | None
    memory_total_bytes: int
    memory_available_bytes: int
    disk_total_bytes: int
    disk_free_bytes: int
    boot_time_utc: datetime
    uptime_seconds: int
