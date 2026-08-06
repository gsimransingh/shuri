"""Explicit share-safe report transformation."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from shuri.models import Report

_REDACTED = "[redacted]"
_SENSITIVE_KEYS = {
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


def redact_report(report: Report) -> Report:
    """Return a copy with collected workstation and network identifiers removed."""
    results = tuple(
        replace(result, metrics=_redact_mapping(result.metrics)) for result in report.results
    )
    return replace(report, hostname=_REDACTED, results=results, redacted=True)


def _redact_mapping(values: dict[str, Any]) -> dict[str, Any]:
    return {key: _redact_value(key, value) for key, value in values.items()}


def _redact_value(key: str, value: Any) -> Any:
    if key in _SENSITIVE_KEYS:
        if isinstance(value, list):
            return []
        if value is None:
            return None
        return _REDACTED
    if isinstance(value, dict):
        return _redact_mapping(value)
    if isinstance(value, list):
        return [_redact_mapping(item) if isinstance(item, dict) else item for item in value]
    return value
