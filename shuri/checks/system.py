"""Operating-system identity and uptime diagnostics."""

from __future__ import annotations

import platform
from datetime import UTC, datetime

import psutil

from shuri.models import CheckResult, CheckStatus


def check_system() -> CheckResult:
    """Collect OS metadata that is useful in a support handoff."""
    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=UTC)
    uptime = datetime.now(UTC) - boot_time
    uptime_days = uptime.total_seconds() / 86_400
    return CheckResult(
        name="system",
        title="Operating System",
        status=CheckStatus.PASS,
        summary=f"{platform.system()} {platform.release()} has been up for {uptime_days:.1f} days.",
        metrics={
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "edition": platform.platform(),
            "machine": platform.machine(),
            "boot_time": boot_time.isoformat(),
            "uptime_seconds": round(uptime.total_seconds()),
        },
    )
