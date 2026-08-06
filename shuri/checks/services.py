"""Status checks for selected Windows services."""

from __future__ import annotations

from shuri.core.policy import DEFAULT_POLICY
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import (
    CommandResult,
    OperatingSystem,
    command_failure_message,
    operating_system,
    run_command,
)

_SERVICES = {
    "wuauserv": "Windows Update",
    "WinDefend": "Microsoft Defender Antivirus",
    "eventlog": "Windows Event Log",
    "BITS": "Background Intelligent Transfer Service",
    "Dhcp": "DHCP Client",
    "Dnscache": "DNS Client",
}
_CRITICAL_SERVICES = {"eventlog", "WinDefend", "Dhcp", "Dnscache"}


def _service_state(name: str) -> tuple[str, CommandResult]:
    result = run_command(("sc", "query", name))
    if not result.succeeded:
        return "unavailable", result
    return ("running" if "RUNNING" in result.output else "stopped"), result


def check_services() -> CheckResult:
    """Inspect native support services without changing service state."""
    active_os = operating_system()
    if active_os is OperatingSystem.LINUX:
        from shuri.checks.native_unix import check_linux_services

        return check_linux_services()
    if active_os is OperatingSystem.MACOS:
        from shuri.checks.native_unix import check_macos_services

        return check_macos_services()
    if active_os is not OperatingSystem.WINDOWS:
        from shuri.checks.native_unix import unsupported_native_check

        return unsupported_native_check("services", "System Services", active_os)
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
