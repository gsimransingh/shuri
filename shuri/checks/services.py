"""Status checks for selected Windows services."""

from __future__ import annotations

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


def _parse_service_state(output: str) -> str:
    """Translate ``sc query`` output into a stable state without guessing."""
    for line in output.splitlines():
        label, separator, value = line.partition(":")
        if separator and label.strip().upper() == "STATE":
            parts = value.split()
            token = parts[-1].upper() if parts else ""
            if token == "RUNNING":
                return "running"
            if token in _STARTING_STATES:
                return "starting"
            if token in _NOT_RUNNING_STATES:
                return "stopped"
    return "unavailable"


def _service_state(name: str) -> tuple[str, CommandResult]:
    result = run_command(("sc", "query", name))
    if not result.succeeded:
        return "unavailable", result
    return _parse_service_state(result.output), result


def check_services() -> CheckResult:
    """Inspect selected Windows support services without changing service state."""
    if not is_windows():
        return CheckResult(
            name="services",
            title="Windows Services",
            status=CheckStatus.UNKNOWN,
            summary="Windows service diagnostics are not available on this platform.",
        )
    queries = {name: _service_state(name) for name in _SERVICES}
    states = {name: state for name, (state, _) in queries.items()}
    unavailable = all(state == "unavailable" for state in states.values())
    if unavailable:
        return CheckResult(
            name="services",
            title="Windows Services",
            status=CheckStatus.UNKNOWN,
            summary=command_failure_message(
                "Windows service status", next(iter(queries.values()))[1]
            ),
            metrics={"services": states},
        )
    stopped_critical = [
        name for name, state in states.items() if state == "stopped" and name in _CRITICAL_SERVICES
    ]
    stopped_noncritical = [
        name
        for name, state in states.items()
        if state == "stopped" and name not in _CRITICAL_SERVICES
    ]
    findings = tuple(
        f"{_SERVICES[name]} is not running." for name in (*stopped_critical, *stopped_noncritical)
    )
    deductions = tuple(
        ScoreDeduction(
            f"Critical service {_SERVICES[name]} is not running",
            DEFAULT_POLICY.stopped_service_points,
            "services",
        )
        for name in stopped_critical
    )
    status = (
        CheckStatus.FAIL
        if stopped_critical
        else CheckStatus.WARNING if stopped_noncritical else CheckStatus.PASS
    )
    return CheckResult(
        name="services",
        title="Windows Services",
        status=status,
        summary=f"Checked {len(_SERVICES)} Windows services.",
        metrics={
            "services": {
                name: {"display_name": _SERVICES[name], "state": state}
                for name, state in states.items()
            }
        },
        findings=findings,
        deductions=deductions,
    )
