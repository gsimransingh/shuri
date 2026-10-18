"""Status checks for selected Windows services."""

from __future__ import annotations

import time
from dataclasses import dataclass

import psutil

from shuri.core.policy import DEFAULT_POLICY
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import CommandResult, command_failure_message, is_windows, run_command

_SERVICES = {
    "wuauserv": "Windows Update",
    "WinDefend": "Microsoft Defender Antivirus",
    "eventlog": "Windows Event Log",
    "BITS": "Background Intelligent Transfer Service",
    "Dhcp": "DHCP Client",
    "Dnscache": "DNS Client",
}
_CRITICAL_SERVICES = {"eventlog", "WinDefend", "Dhcp", "Dnscache"}


_STARTING_STATES = {"START_PENDING", "CONTINUE_PENDING"}
_NOT_RUNNING_STATES = {"STOPPED", "STOP_PENDING", "PAUSE_PENDING", "PAUSED"}
# ``sc qc`` prints a locale-neutral numeric START_TYPE code before its label.
_START_TYPES = {"0": "boot", "1": "system", "2": "auto", "3": "manual", "4": "disabled"}
_STARTING_RECHECKS = 2
_STARTING_RECHECK_SECONDS = 1.0
# Delayed-start services legitimately stay stopped for a few minutes after boot.
_DELAYED_START_GRACE_SECONDS = 300


@dataclass(frozen=True, slots=True)
class _ServiceStatus:
    state: str
    start_type: str
    result: CommandResult


def _parse_service_state(output: str) -> str:
    """Translate ``sc query`` output into a stable state without guessing."""
    for line in output.splitlines():
        label, separator, value = line.partition(":")
        if separator and label.strip().upper() == "STATE":
            parts = value.split()
            token = parts[-1].upper() if parts else ""
            if token == "RUNNING":  # noqa: S105  (a parsed state word, not a secret)
                return "running"
            if token in _STARTING_STATES:
                return "starting"
            if token in _NOT_RUNNING_STATES:
                return "stopped"
    return "unavailable"


def _parse_start_type(output: str) -> str:
    """Translate ``sc qc`` output into a start type, or ``unknown`` when unreadable."""
    for line in output.splitlines():
        label, separator, value = line.partition(":")
        if separator and label.strip().upper() == "START_TYPE":
            parts = value.split()
            kind = _START_TYPES.get(parts[0]) if parts else None
            if kind is None:
                return "unknown"
            return "delayed_auto" if kind == "auto" and "DELAYED" in value.upper() else kind
    return "unknown"


def _service_state(name: str) -> tuple[str, CommandResult]:
    result = run_command(("sc", "query", name))
    if not result.succeeded:
        return "unavailable", result
    return _parse_service_state(result.output), result


def _service_start_type(name: str) -> str:
    result = run_command(("sc", "qc", name))
    return _parse_start_type(result.output) if result.succeeded else "unknown"


def _inspect_service(name: str) -> _ServiceStatus:
    """Read a service's state, giving a service that is still starting time to settle."""
    state, result = _service_state(name)
    for _ in range(_STARTING_RECHECKS):
        if state != "starting":
            break
        time.sleep(_STARTING_RECHECK_SECONDS)
        state, result = _service_state(name)
    start_type = _service_start_type(name) if state != "unavailable" else "unknown"
    return _ServiceStatus(state, start_type, result)


def _seconds_since_boot() -> float | None:
    try:
        return max(0.0, time.time() - psutil.boot_time())
    except (OSError, psutil.Error):
        return None


def _problem(name: str, status: _ServiceStatus, uptime_seconds: float | None) -> str | None:
    """Describe why a service needs attention, or return None when its state is expected.

    A stopped on-demand (manual-start) service is normal: Windows Update and BITS
    are started by Windows only when needed, so "stopped" alone is not a fault.
    """
    if status.state == "starting":
        return "is still starting"
    if status.state != "stopped":
        return None
    if status.start_type == "disabled":
        return "is disabled"
    if (
        status.start_type == "delayed_auto"
        and uptime_seconds is not None
        and uptime_seconds < _DELAYED_START_GRACE_SECONDS
    ):
        return None
    if name in _CRITICAL_SERVICES:
        return "is not running"
    if status.start_type == "manual":
        return None
    if status.start_type == "unknown":
        return "is not running (start type unavailable)"
    return "is not running"


def check_services() -> CheckResult:
    """Inspect selected Windows support services without changing service state."""
    if not is_windows():
        return CheckResult(
            name="services",
            title="Windows Services",
            status=CheckStatus.UNKNOWN,
            summary="Windows service diagnostics are not available on this platform.",
        )
    inspected = {name: _inspect_service(name) for name in _SERVICES}
    if all(status.state == "unavailable" for status in inspected.values()):
        return CheckResult(
            name="services",
            title="Windows Services",
            status=CheckStatus.UNKNOWN,
            summary=command_failure_message(
                "Windows service status", next(iter(inspected.values())).result
            ),
            metrics={"services": {name: status.state for name, status in inspected.items()}},
        )
    uptime = _seconds_since_boot()
    problems = {
        name: problem
        for name, status in inspected.items()
        if (problem := _problem(name, status, uptime)) is not None
    }
    critical = [
        name
        for name, problem in problems.items()
        if name in _CRITICAL_SERVICES and "starting" not in problem
    ]
    findings = tuple(
        f"{_SERVICES[name]} {problem}."
        for name, problem in sorted(problems.items(), key=lambda item: item[0] not in critical)
    )
    deductions = tuple(
        ScoreDeduction(
            f"Critical service {_SERVICES[name]} {problems[name]}",
            DEFAULT_POLICY.stopped_service_points,
            "services",
        )
        for name in critical
    )
    status = CheckStatus.FAIL if critical else CheckStatus.WARNING if problems else CheckStatus.PASS
    return CheckResult(
        name="services",
        title="Windows Services",
        status=status,
        summary=f"Checked {len(_SERVICES)} Windows services.",
        metrics={
            "services": {
                name: {
                    "display_name": _SERVICES[name],
                    "state": item.state,
                    "start_type": item.start_type,
                }
                for name, item in inspected.items()
            }
        },
        findings=findings,
        deductions=deductions,
    )
