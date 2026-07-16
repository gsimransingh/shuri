from __future__ import annotations

import platform
from datetime import datetime, timezone
from pathlib import Path

import psutil

from shuri.models.system import SystemInfo


class SystemInfoCollectionError(RuntimeError):
    """Raised when the local system snapshot cannot be collected."""


def collect_system_info(
    *,
    disk_path: str | Path | None = None,
    now: datetime | None = None,
) -> SystemInfo:
    """Collect a system snapshot using only local, read-only operating system APIs."""
    collected_at = now or datetime.now(timezone.utc)
    if collected_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    target_path = Path(disk_path) if disk_path is not None else _default_disk_path()

    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(target_path))
        boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
        physical_cores = psutil.cpu_count(logical=False)
        logical_cores = psutil.cpu_count(logical=True)
    except (OSError, psutil.Error) as exc:
        raise SystemInfoCollectionError(str(exc)) from exc

    uname = platform.uname()
    uptime_seconds = max(0, int((collected_at - boot_time).total_seconds()))

    return SystemInfo(
        hostname=uname.node or "Unknown",
        os_name=uname.system or "Unknown",
        os_release=uname.release or "Unknown",
        os_version=uname.version or "Unknown",
        architecture=uname.machine or "Unknown",
        processor=uname.processor or platform.processor() or uname.machine or "Unknown",
        python_version=platform.python_version(),
        physical_cores=physical_cores,
        logical_cores=logical_cores,
        memory_total_bytes=memory.total,
        memory_available_bytes=memory.available,
        disk_total_bytes=disk.total,
        disk_free_bytes=disk.free,
        boot_time_utc=boot_time,
        uptime_seconds=uptime_seconds,
    )


def _default_disk_path() -> Path:
    current_directory = Path.cwd()
    return Path(current_directory.anchor or "/")
