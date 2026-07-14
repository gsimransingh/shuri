"""Status checks for selected Windows services."""

from __future__ import annotations

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import is_windows, run_command

_SERVICES = {
    "wuauserv": "Windows Update",
    "WinDefend": "Microsoft Defender Antivirus",
    "eventlog": "Windows Event Log",
    "BITS": "Background Intelligent Transfer Service",
    "Dhcp": "DHCP Client",
    "Dnscache": "DNS Client",
}
_CRITICAL_SERVICES = {"eventlog", "WinDefend", "Dhcp", "Dnscache"}


def _service_state(name: str) -> str:
    output = run_command(("sc", "query", name))
    if output is None:
        return "unavailable"
    return "running" if "RUNNING" in output else "stopped"


def check_services() -> CheckResult:
    """Inspect selected Windows support services without changing service state."""
    if not is_windows():
        return CheckResult(
            name="services",
            title="Windows Services",
            status=CheckStatus.UNKNOWN,
            summary="Windows service diagnostics are not available on this platform.",
        )
    states = {name: _service_state(name) for name in _SERVICES}
    unavailable = all(state == "unavailable" for state in states.values())
    if unavailable:
        return CheckResult(
            name="services",
            title="Windows Services",
            status=CheckStatus.UNKNOWN,
            summary="Windows services could not be queried.",
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
        ScoreDeduction(f"Critical service {_SERVICES[name]} is not running", 8, "services")
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
