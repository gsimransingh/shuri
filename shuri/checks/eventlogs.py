"""Structured Windows event-log health summary."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from shuri.core.policy import DEFAULT_POLICY
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import command_failure_message, is_windows, run_powershell

_MAX_EVENTS = 200
_MAX_INCIDENTS_SHOWN = 25
_LEVEL_NAMES = {1: "Critical", 2: "Error", 3: "Warning"}


def _level(entry: dict[str, Any]) -> int | None:
    """Return a recognised numeric event level, or None for anything else."""
    level = entry.get("Level")
    if isinstance(level, int) and not isinstance(level, bool) and level in _LEVEL_NAMES:
        return level
    return None


def _entries(payload: str) -> list[dict[str, Any]] | None:
    try:
        parsed: Any = json.loads(payload)
    except json.JSONDecodeError:
        return None
    entries = parsed if isinstance(parsed, list) else [parsed]
    if not all(isinstance(entry, dict) for entry in entries):
        return None
    return entries


def parse_event_levels(payload: str) -> tuple[int, int, int, bool] | None:
    """Count raw event levels from PowerShell JSON and expose truncation."""
    entries = _entries(payload)
    if entries is None:
        return None
    truncated = len(entries) > _MAX_EVENTS
    levels = [_level(entry) for entry in entries[:_MAX_EVENTS]]
    return levels.count(1), levels.count(2), levels.count(3), truncated


def _event_time(entry: dict[str, Any]) -> datetime | None:
    value = entry.get("TimeCreated")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def group_event_incidents(payload: str) -> tuple[dict[str, object], ...]:
    """Collapse bursts of identical events into incidents, newest first.

    Events with the same level, provider and ID that fall within the burst window
    of the first event in a run are one incident, so one boot-time burst of 35
    identical entries is counted once. A steady repeating fault still produces many
    incidents. Events without a parseable timestamp are never merged.
    """
    entries = _entries(payload)
    if entries is None:
        return ()
    window = timedelta(seconds=DEFAULT_POLICY.event_burst_window_seconds)
    dated: dict[tuple[int, object, object], list[tuple[datetime, dict[str, Any]]]] = {}
    incidents: list[tuple[datetime | None, dict[str, object]]] = []
    for entry in entries[:_MAX_EVENTS]:
        level = _level(entry)
        if level is None:
            continue
        key = (level, entry.get("Id"), entry.get("ProviderName"))
        moment = _event_time(entry)
        if moment is None:
            incidents.append((None, _incident(entry, level, 1)))
        else:
            dated.setdefault(key, []).append((moment, entry))
    for (level, _, _), occurrences in dated.items():
        occurrences.sort(key=lambda item: item[0])
        anchor = occurrences[0][0]
        count = 0
        latest = occurrences[0]
        for moment, entry in occurrences:
            if moment - anchor > window:
                incidents.append((latest[0], _incident(latest[1], level, count)))
                anchor, count = moment, 0
            count += 1
            latest = (moment, entry)
        incidents.append((latest[0], _incident(latest[1], level, count)))
    incidents.sort(key=lambda item: item[0] or datetime.min.replace(tzinfo=UTC), reverse=True)
    return tuple(incident for _, incident in incidents)


def _is_high_signal(entry: dict[str, Any], level: int) -> bool:
    provider = entry.get("ProviderName")
    return (
        level == 2
        and isinstance(provider, str)
        and provider.casefold() in DEFAULT_POLICY.high_signal_event_providers
    )


def _incident(entry: dict[str, Any], level: int, count: int) -> dict[str, object]:
    return {
        "time_created": entry.get("TimeCreated", "Unavailable"),
        "level": _LEVEL_NAMES[level],
        "event_id": entry.get("Id", "Unavailable"),
        "provider": entry.get("ProviderName", "Unavailable"),
        "count": count,
        "high_signal": _is_high_signal(entry, level),
    }


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
    incidents = group_event_incidents(result.output)
    error_incidents = sum(1 for incident in incidents if incident["level"] == "Error")
    flagged = [incident for incident in incidents if incident["high_signal"]]
    event_details = incidents[:_MAX_INCIDENTS_SHOWN]
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
    if len(flagged) >= DEFAULT_POLICY.high_signal_error_incident_count:
        status = CheckStatus.WARNING if status is CheckStatus.PASS else status
        sources = sorted({f"{item['provider']} (event {item['event_id']})" for item in flagged})
        findings.append(
            f"{len(flagged)} storage or hardware error incident(s) found: "
            f"{', '.join(sources[:3])}{' and more' if len(sources) > 3 else ''}."
        )
        deductions.append(
            ScoreDeduction(
                "Storage, file-system or hardware errors were logged",
                DEFAULT_POLICY.high_signal_error_points,
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
        summary=(
            f"Last 24 hours: {critical} critical, {errors} errors "
            f"({error_incidents} incidents), {warnings} warnings."
        ),
        metrics={
            "critical": critical,
            "errors": errors,
            "error_incidents": error_incidents,
            "high_signal_incidents": len(flagged),
            "warnings": warnings,
            "window_hours": 24,
            "truncated": truncated,
            "maximum_events": _MAX_EVENTS,
            "recent_events": list(event_details),
        },
        findings=tuple(findings),
        deductions=tuple(deductions),
    )
