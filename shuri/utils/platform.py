"""Narrow wrappers around platform-specific behaviour."""

from __future__ import annotations

import os
import platform
import subprocess
from collections.abc import Sequence


def is_windows() -> bool:
    """Return whether Shuri is running on Windows."""
    return platform.system() == "Windows"


def system_drive() -> str:
    """Return the primary system-drive mount point for the active platform."""
    if is_windows():
        return os.environ.get("SYSTEMDRIVE", "C:") + "\\"
    return "/"


def run_command(command: Sequence[str], timeout: float = 5.0) -> str | None:
    """Run a fixed command safely and return stdout, or ``None`` on failure."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout if completed.returncode == 0 else None


def run_powershell(script: str, timeout: float = 5.0) -> str | None:
    """Run a read-only Windows PowerShell command, or return ``None`` on failure."""
    if not is_windows():
        return None
    return run_command(
        ("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script),
        timeout=timeout,
    )
