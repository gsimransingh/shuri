"""Throw malformed and hostile input at every parser: none may crash or return nonsense."""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from typing import Any

import pytest

from shuri.checks.antivirus import _parse_timestamp, _signature_age_days
from shuri.checks.battery import parse_battery_report
from shuri.checks.eventlogs import group_event_incidents, parse_event_levels
from shuri.checks.network import parse_windows_network_configuration
from shuri.checks.physical_drives import build_physical_drive_result, parse_physical_drives
from shuri.checks.services import _parse_service_state, _parse_start_type
from shuri.core.privacy import redact_report
from shuri.models import CheckResult, CheckStatus, Report

_ITERATIONS = 400
_KEYS = (
    "Level",
    "Id",
    "ProviderName",
    "TimeCreated",
    "DeviceId",
    "FriendlyName",
    "SizeBytes",
    "OperationalStatus",
    "HealthStatus",
    "TemperatureCelsius",
    "WearPercent",
    "Gateway",
    "DnsServers",
    "PendingUpdates",
    "AntivirusSignatureLastUpdated",
)
_STRINGS = (
    "",
    "0",
    "-1",
    "NaN",
    "Infinity",
    "/Date(0)/",
    "/Date(99999999999999999999)/",
    "2026-13-45T99:99:99Z",
    "2026-01-01T00:00:00",
    "\x00\x01",
    "‮ rtl",
    "A" * 5000,
    "%s%n",
    "' OR 1=1 --",
)


def _scalar(rng: random.Random) -> Any:
    return rng.choice(
        (
            None,
            True,
            False,
            0,
            -1,
            1,
            2,
            3,
            10**30,
            -(10**30),
            1.5,
            float("inf"),
            float("-inf"),
            float("nan"),
            rng.choice(_STRINGS),
        )
    )


def _value(rng: random.Random, depth: int = 0) -> Any:
    roll = rng.random()
    if depth < 3 and roll < 0.25:
        return [_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    if depth < 3 and roll < 0.5:
        return {
            rng.choice(_KEYS + _STRINGS[:4]): _value(rng, depth + 1)
            for _ in range(rng.randint(0, 6))
        }
    return _scalar(rng)


def _payloads(seed: int) -> list[str]:
    rng = random.Random(seed)
    payloads = ["", " ", "null", "[]", "{}", "[[]]", '{"a":', "\x00", "not json", "[1,2,3]"]
    for _ in range(_ITERATIONS):
        text = json.dumps(_value(rng), allow_nan=True)
        payloads.append(text)
        payloads.append(text[: rng.randint(0, len(text))])  # truncated mid-token
    return payloads


def test_physical_drive_parser_and_assessment_survive_hostile_json() -> None:
    for payload in _payloads(1):
        drives = parse_physical_drives(payload)

        assert isinstance(drives, tuple)
        result = build_physical_drive_result(drives)
        assert isinstance(result.status, CheckStatus)


def test_event_log_parsers_survive_hostile_json() -> None:
    for payload in _payloads(2):
        counts = parse_event_levels(payload)
        incidents = group_event_incidents(payload)

        assert counts is None or all(isinstance(item, int | bool) for item in counts)
        assert isinstance(incidents, tuple)


def test_network_configuration_parser_survives_hostile_json() -> None:
    for payload in _payloads(3):
        gateway, servers = parse_windows_network_configuration(payload)

        assert gateway is None or isinstance(gateway, str)
        assert all(isinstance(server, str) for server in servers)


def test_battery_report_parser_survives_arbitrary_text() -> None:
    rng = random.Random(4)
    for _ in range(_ITERATIONS):
        text = "".join(
            rng.choice(("DESIGN CAPACITY", "mWh", "12,345", " ", "\n", "x", "9" * 40))
            for _ in range(30)
        )

        design, full = parse_battery_report(text)

        assert design is None or design >= 0
        assert full is None or full >= 0


def test_timestamp_parsers_survive_arbitrary_values() -> None:
    rng = random.Random(5)
    for _ in range(_ITERATIONS):
        value = _value(rng)

        parsed = _parse_timestamp(value)
        age = _signature_age_days(value)

        assert parsed is None or parsed.tzinfo is not None
        assert age is None or age >= 0


@pytest.mark.parametrize("parser", (_parse_service_state, _parse_start_type))
def test_service_translators_survive_arbitrary_strings(parser: Callable[[str], str]) -> None:
    rng = random.Random(6)
    for _ in range(_ITERATIONS):
        text = "".join(
            rng.choice(("running", "AUTO", "_", " ", "\x00", "é", "pending")) for _ in range(8)
        )

        assert isinstance(parser(text), str)


def test_redaction_survives_arbitrary_metrics_and_never_leaks_the_hostname() -> None:
    rng = random.Random(7)
    for _ in range(_ITERATIONS):
        metrics = {
            rng.choice(_KEYS + ("hostname", "name", "services", "adapters")): _value(rng)
            for _ in range(rng.randint(1, 5))
        }
        metrics["hostname"] = "canary-host-9137"
        result = CheckResult("x", "X", CheckStatus.PASS, "on canary-host-9137", metrics=metrics)
        report = Report.create((result,), "canary-host-9137")

        redacted = redact_report(report)

        assert "canary-host-9137" not in json.dumps(redacted.to_dict(), default=str)
