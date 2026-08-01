"""Narrow wrappers around platform-specific behaviour."""

from __future__ import annotations

import os
import platform
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


def is_windows() -> bool:
    """Return whether Shuri is running on Windows."""
    return platform.system() == "Windows"


def system_drive() -> str:
    """Return the primary system-drive mount point for the active platform."""
    if is_windows():
        return os.environ.get("SYSTEMDRIVE", "C:") + "\\"
    return "/"


class CommandFailure(StrEnum):
    """Stable failure categories exposed by platform command wrappers."""

    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    ACCESS_DENIED = "access_denied"
    EXIT_CODE = "exit_code"
    OS_ERROR = "os_error"


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Output or a classified failure from a fixed, shell-free command."""

    output: str = ""
    failure: CommandFailure | None = None
    exit_code: int | None = None

    @property
    def succeeded(self) -> bool:
        return self.failure is None


def run_command(command: Sequence[str], timeout: float = 5.0) -> CommandResult:
    """Run a fixed command safely without a shell and classify any failure."""
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
    except subprocess.TimeoutExpired:
        return CommandResult(failure=CommandFailure.TIMEOUT)
    except FileNotFoundError:
        return CommandResult(failure=CommandFailure.NOT_FOUND)
    except PermissionError:
        return CommandResult(failure=CommandFailure.ACCESS_DENIED)
    except OSError:
        return CommandResult(failure=CommandFailure.OS_ERROR)
    if completed.returncode == 0:
        return CommandResult(output=completed.stdout)
    denied = completed.returncode == 5 or "access denied" in completed.stderr.casefold()
    return CommandResult(
        failure=CommandFailure.ACCESS_DENIED if denied else CommandFailure.EXIT_CODE,
        exit_code=completed.returncode,
    )


def run_powershell(script: str, timeout: float = 5.0) -> CommandResult:
    """Run a read-only Windows PowerShell command and classify failures."""
    if not is_windows():
        return CommandResult(failure=CommandFailure.NOT_FOUND)
    return run_command(
        ("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script),
        timeout=timeout,
    )


def command_failure_message(subject: str, result: CommandResult) -> str:
    """Return safe, actionable guidance without exposing command contents."""
    if result.failure is None:
        return f"{subject} returned no usable data."
    messages = {
        CommandFailure.TIMEOUT: f"{subject} timed out; try again in a few minutes.",
        CommandFailure.NOT_FOUND: f"{subject} is unavailable on this system.",
        CommandFailure.ACCESS_DENIED: f"{subject} was denied; run Shuri with sufficient access.",
        CommandFailure.EXIT_CODE: f"{subject} failed; verify the related Windows component.",
        CommandFailure.OS_ERROR: f"{subject} could not be started by the operating system.",
    }
    return messages[result.failure]
