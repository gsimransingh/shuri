"""Structured Windows event-log health summary."""

from __future__ import annotations

import json
from typing import Any

from shuri.core.policy import DEFAULT_POLICY
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import command_failure_message, is_windows, run_powershell

_MAX_EVENTS = 50
_LEVEL_NAMES = {1: "Critical", 2: "Error", 3: "Warning"}


def parse_event_levels(payload: str) -> tuple[int, int, int, bool] | None:
    """Count numeric event levels from PowerShell JSON and expose truncation."""
    try:
        parsed: Any = json.loads(payload)
    except json.JSONDecodeError:
        return None
    entries = parsed if isinstance(parsed, list) else [parsed]
    if not all(isinstance(entry, dict) for entry in entries):
        return None
    levels = [entry.get("Level") for entry in entries]
    truncated = len(levels) > _MAX_EVENTS
    levels = levels[:_MAX_EVENTS]
    return levels.count(1), levels.count(2), levels.count(3), truncated


def parse_event_details(payload: str) -> tuple[dict[str, object], ...]:
    """Return bounded, non-message event metadata suitable for detailed display."""
    try:
        parsed: Any = json.loads(payload)
    except json.JSONDecodeError:
        return ()
    entries = parsed if isinstance(parsed, list) else [parsed]
    details: list[dict[str, object]] = []
    for entry in entries[:_MAX_EVENTS]:
        if not isinstance(entry, dict) or entry.get("Level") not in _LEVEL_NAMES:
            continue
        details.append(
            {
                "time_created": entry.get("TimeCreated", "Unavailable"),
                "level": _LEVEL_NAMES[int(entry["Level"])],
                "event_id": entry.get("Id", "Unavailable"),
                "provider": entry.get("ProviderName", "Unavailable"),
            }
        )
    return tuple(details)


def check_event_logs() -> CheckResult:
    """Summarise critical, error, and warning System events from the last day."""
    if not is_windows():
        return CheckResult(
            name="eventlogs",
            title="Event Logs",
            status=CheckStatus.UNKNOWN,
            summary="Windows event-log diagnostics are not available on this platform.",
        )
    script = (
        "$ErrorActionPreference = 'Stop'; try { "
        "$events = @(Get-WinEvent -FilterHashtable "
        "@{LogName='System'; Level=1,2,3; StartTime=(Get-Date).AddHours(-24)} "
        f"-MaxEvents {_MAX_EVENTS + 1}) "
        "} catch { if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') "
        "{ $events = @() } else { throw } }; "
        "$selected = @($events | Select-Object Level, Id, ProviderName, "
        "@{Name='TimeCreated';Expression={$_.TimeCreated.ToUniversalTime().ToString('o')}}); "
        "ConvertTo-Json -InputObject $selected -Compress"
    )
    result = run_powershell(script, timeout=8)
    if not result.succeeded:
        return CheckResult(
            name="eventlogs",
            title="Event Logs",
            status=CheckStatus.UNKNOWN,
            summary=command_failure_message("Windows System event log", result),
        )
    counts = parse_event_levels(result.output)
    if counts is None:
        return CheckResult(
            name="eventlogs",
            title="Event Logs",
            status=CheckStatus.UNKNOWN,
            summary="The Windows System event log returned invalid structured data.",
        )
    critical, errors, warnings, truncated = counts
    event_details = parse_event_details(result.output)
    deductions: list[ScoreDeduction] = []
    findings: list[str] = []
    status = CheckStatus.PASS
    if critical:
        status = CheckStatus.FAIL
        findings.append(f"{critical} recent critical System event(s) found.")
        deductions.append(
            ScoreDeduction(
                "Recent critical System events were found",
                DEFAULT_POLICY.critical_event_points,
                "eventlogs",
            )
        )
    if errors >= DEFAULT_POLICY.repeated_error_event_count:
        status = CheckStatus.WARNING if status is CheckStatus.PASS else status
        findings.append(f"{errors} recent error System event(s) found.")
        deductions.append(
            ScoreDeduction(
                "Five or more recent System errors were found",
                DEFAULT_POLICY.repeated_error_event_points,
                "eventlogs",
            )
        )
    if truncated:
        findings.append(
            f"More than {_MAX_EVENTS} matching events exist; counts show the newest {_MAX_EVENTS}."
        )
    return CheckResult(
        name="eventlogs",
        title="Event Logs",
        status=status,
        summary=f"Last 24 hours: {critical} critical, {errors} errors, {warnings} warnings.",
        metrics={
            "critical": critical,
            "errors": errors,
            "warnings": warnings,
            "window_hours": 24,
            "truncated": truncated,
            "maximum_events": _MAX_EVENTS,
            "recent_events": list(event_details),
        },
        findings=tuple(findings),
        deductions=tuple(deductions),
    )
