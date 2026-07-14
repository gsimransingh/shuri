"""A deliberately small Windows event-log health summary."""

from __future__ import annotations

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import is_windows, run_command

_QUERY = (
    "*[System[(Level=1 or Level=2 or Level=3) and TimeCreated[timediff(@SystemTime) <= 86400000]]]"
)


def check_event_logs() -> CheckResult:
    """Summarise critical, error, and warning System events from the last day."""
    if not is_windows():
        return CheckResult(
            name="eventlogs",
            title="Event Logs",
            status=CheckStatus.UNKNOWN,
            summary="Windows event-log diagnostics are not available on this platform.",
        )
    output = run_command(
        ("wevtutil", "qe", "System", f"/q:{_QUERY}", "/c:50", "/f:text"), timeout=8
    )
    if output is None:
        return CheckResult(
            name="eventlogs",
            title="Event Logs",
            status=CheckStatus.UNKNOWN,
            summary="The Windows System event log could not be queried.",
        )
    critical = output.count("Level: Critical")
    errors = output.count("Level: Error")
    warnings = output.count("Level: Warning")
    deductions: list[ScoreDeduction] = []
    findings: list[str] = []
    status = CheckStatus.PASS
    if critical:
        status = CheckStatus.FAIL
        findings.append(f"{critical} recent critical System event(s) found.")
        deductions.append(
            ScoreDeduction("Recent critical System events were found", 10, "eventlogs")
        )
    if errors >= 5:
        status = CheckStatus.WARNING if status is CheckStatus.PASS else status
        findings.append(f"{errors} recent error System event(s) found.")
        deductions.append(
            ScoreDeduction("Five or more recent System errors were found", 5, "eventlogs")
        )
    return CheckResult(
        name="eventlogs",
        title="Event Logs",
        status=status,
        summary=f"Last 24 hours: {critical} critical, {errors} errors, {warnings} warnings.",
        metrics={"critical": critical, "errors": errors, "warnings": warnings, "window_hours": 24},
        findings=tuple(findings),
        deductions=tuple(deductions),
    )
