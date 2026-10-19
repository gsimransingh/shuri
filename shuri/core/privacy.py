"""Explicit share-safe report transformation.

Redaction fails closed: a metric survives only if its key is on ``SAFE_METRIC_KEYS``, so a new
field added to a check is hidden until someone reviews it and adds it here. Identifier values
collected from the report are also removed from free text such as summaries and findings.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from typing import Any

from shuri.models import CheckResult, HealthAssessment, Report, ScoreDeduction

REDACTED = "[redacted]"

type Scrubber = Callable[[str], str]

# Keys whose values name a workstation, user, network, or device. Values found under them are
# also scrubbed from free text. Everything not in SAFE_METRIC_KEYS is redacted regardless.
IDENTIFIER_KEYS = frozenset(
    {
        "addresses",
        "default_gateway",
        "device_id",
        "dns_servers",
        "hostname",
        "mac_address",
        "name",
        "process_id",
        "process_name",
        "target",
        "user",
        "username",
    }
)

SAFE_METRIC_KEYS = frozenset(
    {
        # cpu / memory / system
        "model",
        "architecture",
        "physical_cores",
        "logical_cores",
        "utilisation_percent",
        "frequency_mhz",
        "load_average",
        "total_bytes",
        "available_bytes",
        "used_bytes",
        "available_percent",
        "swap_total_bytes",
        "swap_used_bytes",
        "swap_percent",
        "system",
        "release",
        "version",
        "edition",
        "machine",
        "processor",
        "memory_total_bytes",
        "memory_available_bytes",
        "system_disk_total_bytes",
        "system_disk_free_bytes",
        "python_version",
        "boot_time",
        "uptime_seconds",
        # disk
        "filesystems",
        "device",
        "mountpoint",
        "filesystem",
        "free_bytes",
        "used_percent",
        # physical drives
        "physical_drives",
        "media_type",
        "bus_type",
        "health_status",
        "operational_status",
        "size_bytes",
        "temperature_celsius",
        "wear_percent",
        "read_errors_total",
        "write_errors_total",
        "power_on_hours",
        # network (addresses, names, gateway, DNS and probe targets are identifiers)
        "adapters",
        "is_up",
        "configuration_complete",
        "probes_run",
        "dns_probe",
        "tcp_probe",
        "succeeded",
        "port",
        # battery
        "charge_percent",
        "power_plugged",
        "seconds_left",
        "design_capacity_mwh",
        "full_charge_capacity_mwh",
        "battery_health_percent",
        # updates
        "pending_reboot",
        "available_updates",
        "update_query_available",
        # antivirus
        "defender",
        "AMServiceEnabled",
        "AntivirusEnabled",
        "RealTimeProtectionEnabled",
        "AntivirusSignatureLastUpdated",
        "signature_age_days",
        "third_party_products",
        # services (the keys of the "services" mapping are fixed Windows service names)
        "services",
        "display_name",
        "state",
        "start_type",
        "wuauserv",
        "WinDefend",
        "eventlog",
        "BITS",
        "Dhcp",
        "Dnscache",
        # event logs
        "critical",
        "errors",
        "error_incidents",
        "warnings",
        "window_hours",
        "truncated",
        "maximum_events",
        "recent_events",
        "time_created",
        "level",
        "event_id",
        "provider",
        "count",
    }
)

_MINIMUM_IDENTIFIER_LENGTH = 3


def redact_report(report: Report) -> Report:
    """Return a copy with workstation and network identifiers removed."""
    identifiers = _collect_identifiers(report)
    scrub = _text_scrubber(identifiers)
    results = tuple(_redact_result(result, scrub) for result in report.results)
    assessment = _redact_assessment(report.assessment, scrub)
    return replace(report, hostname=REDACTED, results=results, assessment=assessment, redacted=True)


def _redact_result(result: CheckResult, scrub: Scrubber) -> CheckResult:
    return replace(
        result,
        summary=scrub(result.summary),
        metrics=_redact_mapping(result.metrics, scrub),
        findings=tuple(scrub(finding) for finding in result.findings),
        deductions=tuple(_redact_deduction(item, scrub) for item in result.deductions),
    )


def _redact_assessment(
    assessment: HealthAssessment | None, scrub: Scrubber
) -> HealthAssessment | None:
    if assessment is None:
        return None
    return replace(
        assessment,
        deductions=tuple(_redact_deduction(item, scrub) for item in assessment.deductions),
    )


def _redact_deduction(deduction: ScoreDeduction, scrub: Scrubber) -> ScoreDeduction:
    return replace(deduction, reason=scrub(deduction.reason))


def _redact_mapping(values: dict[str, Any], scrub: Scrubber) -> dict[str, Any]:
    return {key: _redact_value(key, value, scrub) for key, value in values.items()}


def _redact_value(key: str, value: Any, scrub: Scrubber) -> Any:
    if key not in SAFE_METRIC_KEYS:
        return None if value is None else REDACTED
    return _scrub_structure(value, scrub)


def _scrub_structure(value: Any, scrub: Scrubber) -> Any:
    if isinstance(value, dict):
        return _redact_mapping(value, scrub)
    if isinstance(value, list | tuple):
        return [_scrub_structure(item, scrub) for item in value]
    if isinstance(value, str):
        return scrub(value)
    return value


def _collect_identifiers(report: Report) -> set[str]:
    found = {report.hostname}
    for result in report.results:
        found.update(_identifier_values(result.metrics))
    return {item for item in found if len(item) >= _MINIMUM_IDENTIFIER_LENGTH}


def _identifier_values(value: Any, *, under_identifier: bool = False) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _identifier_values(item, under_identifier=key in IDENTIFIER_KEYS)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _identifier_values(item, under_identifier=under_identifier)
    elif isinstance(value, str) and under_identifier:
        yield value.strip()


def _text_scrubber(identifiers: set[str]) -> Scrubber:
    if not identifiers:
        return lambda text: text
    ordered = sorted(identifiers, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(item) for item in ordered), re.IGNORECASE)
    return lambda text: pattern.sub(REDACTED, text)
