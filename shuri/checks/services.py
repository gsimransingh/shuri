"""Status checks for selected Windows services."""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass

import psutil

from shuri.core.policy import DEFAULT_POLICY
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import is_windows

_SERVICES = {
    "wuauserv": "Windows Update",
    "WinDefend": "Microsoft Defender Antivirus",
    "eventlog": "Windows Event Log",
    "BITS": "Background Intelligent Transfer Service",
    "Dhcp": "DHCP Client",
    "Dnscache": "DNS Client",
}
_CRITICAL_SERVICES = {"eventlog", "WinDefend", "Dhcp", "Dnscache"}

# psutil reports the Service Control Manager's state names in lower case.
_STARTING_STATES = {"start_pending", "continue_pending"}
_NOT_RUNNING_STATES = {"stopped", "stop_pending", "pause_pending", "paused"}
_START_TYPES = {
    "boot": "boot",
    "system": "system",
    "automatic": "auto",
    "manual": "manual",
    "disabled": "disabled",
}
_STARTING_RECHECKS = 2
_STARTING_RECHECK_SECONDS = 1.0
# Delayed-start services legitimately stay stopped for a few minutes after boot.
_DELAYED_START_GRACE_SECONDS = 300
_SERVICES_REGISTRY_KEY = r"SYSTEM\CurrentControlSet\Services"


@dataclass(frozen=True, slots=True)
class _ServiceStatus:
    state: str
    start_type: str


def _parse_service_state(status: str) -> str:
    """Translate psutil's service status into a stable state without guessing."""
    label = status.lower()
    if label == "running":
        return "running"
    if label in _STARTING_STATES:
        return "starting"
    if label in _NOT_RUNNING_STATES:
        return "stopped"
    return "unavailable"


def _parse_start_type(start_type: str, *, delayed: bool = False) -> str:
    """Translate psutil's start type, or ``unknown`` when it is not one Windows documents."""
    kind = _START_TYPES.get(start_type.lower())
    if kind is None:
        return "unknown"
    return "delayed_auto" if kind == "auto" and delayed else kind


def _is_delayed_autostart(name: str) -> bool:
    """Read the ``DelayedAutostart`` registry flag; any failure means not delayed."""
    try:
        winreg = importlib.import_module("winreg")
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"{_SERVICES_REGISTRY_KEY}\{name}") as key:
            value, _kind = winreg.QueryValueEx(key, "DelayedAutostart")
    except (ImportError, OSError):
        return False
    return bool(value == 1)


def _read_service(name: str) -> tuple[str, str]:
    """Return psutil's raw ``(status, start_type)`` strings for a service."""
    getter = getattr(psutil, "win_service_get", None)
    if getter is None:
        raise OSError("Windows service queries are unavailable on this platform.")
    service = getter(name)
    return str(service.status()), str(service.start_type())


def _service_state(name: str) -> str:
    try:
        return _parse_service_state(_read_service(name)[0])
    except (psutil.Error, OSError):
        return "unavailable"


def _inspect_service(name: str) -> _ServiceStatus:
    """Read a service's state, giving a service that is still starting time to settle."""
    state = _service_state(name)
    for _ in range(_STARTING_RECHECKS):
        if state != "starting":
            break
        time.sleep(_STARTING_RECHECK_SECONDS)
        state = _service_state(name)
    if state == "unavailable":
        return _ServiceStatus(state, "unknown")
    try:
        raw_type = _read_service(name)[1]
    except (psutil.Error, OSError):
        return _ServiceStatus(state, "unknown")
    return _ServiceStatus(state, _parse_start_type(raw_type, delayed=_is_delayed_autostart(name)))


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
            summary="Windows service status could not be read; run Shuri with sufficient access.",
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
