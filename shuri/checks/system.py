"""Operating-system identity and uptime diagnostics."""

from __future__ import annotations

import platform
import socket
from datetime import UTC, datetime

import psutil

from shuri.models import CheckResult, CheckStatus
from shuri.utils.platform import system_drive


def check_system() -> CheckResult:
    """Collect OS metadata that is useful in a support handoff."""
    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=UTC)
    uptime = datetime.now(UTC) - boot_time
    uptime_days = uptime.total_seconds() / 86_400
    memory = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(system_drive())
    except OSError:
        disk = None
    return CheckResult(
        name="system",
        title="System Information",
        status=CheckStatus.PASS,
        summary=f"{platform.system()} {platform.release()} has been up for {uptime_days:.1f} days.",
        metrics={
            "hostname": socket.gethostname(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "edition": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or "Unavailable",
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "memory_total_bytes": memory.total,
            "memory_available_bytes": memory.available,
            "system_disk_total_bytes": disk.total if disk else None,
            "system_disk_free_bytes": disk.free if disk else None,
            "python_version": platform.python_version(),
            "boot_time": boot_time.isoformat(),
            "uptime_seconds": round(uptime.total_seconds()),
        },
    )
