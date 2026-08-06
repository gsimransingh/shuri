"""Microsoft Defender status collection on Windows."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from shuri.core.policy import DEFAULT_POLICY
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import (
    CommandResult,
    OperatingSystem,
    command_failure_message,
    operating_system,
    run_powershell,
)


def _defender_status() -> tuple[dict[str, Any] | None, CommandResult]:
    result = run_powershell(
        "Get-MpComputerStatus | Select-Object "
        "AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,"
        "AntivirusSignatureLastUpdated | ConvertTo-Json -Compress"
    )
    if not result.succeeded:
        return None, result
    try:
        data = json.loads(result.output)
    except json.JSONDecodeError:
        return None, result
    return (data if isinstance(data, dict) else None), result


def _third_party_antivirus_products() -> tuple[str, ...]:
    """Return registered non-Defender antivirus products when Windows exposes them."""
    result = run_powershell(
        "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct | "
        "Select-Object DisplayName | ConvertTo-Json -Compress"
    )
    if not result.succeeded:
        return ()
    try:
        data = json.loads(result.output)
    except json.JSONDecodeError:
        return ()
    entries = data if isinstance(data, list) else [data]
    return tuple(
        str(entry["DisplayName"])
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("DisplayName"), str)
        and "defender" not in entry["DisplayName"].casefold()
    )


def _signature_age_days(value: object) -> int | None:
    """Return whole days since a Defender signature timestamp, when parseable."""
    if not isinstance(value, str):
        return None
    powershell_date = re.fullmatch(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/", value)
    if powershell_date:
        try:
            updated = datetime.fromtimestamp(int(powershell_date.group(1)) / 1000, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        try:
            updated = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return max(0, (datetime.now(UTC) - updated).days)


def check_antivirus() -> CheckResult:
    """Assess native platform security posture without altering it."""
    active_os = operating_system()
    if active_os is OperatingSystem.LINUX:
        from shuri.checks.native_unix import check_linux_security

        return check_linux_security()
    if active_os is OperatingSystem.MACOS:
        from shuri.checks.native_unix import check_macos_security

        return check_macos_security()
    if active_os is not OperatingSystem.WINDOWS:
        from shuri.checks.native_unix import unsupported_native_check

        return unsupported_native_check("antivirus", "Security Posture", active_os)
    status_data, defender_query = _defender_status()
    if status_data is None:
        third_party_products = _third_party_antivirus_products()
        if third_party_products:
            return CheckResult(
                name="antivirus",
                title="Antivirus",
                status=CheckStatus.UNKNOWN,
                summary=(
                    "Third-party antivirus was detected, but its protection state was not verified."
                ),
                metrics={"third_party_products": list(third_party_products)},
                findings=("Verify the registered third-party antivirus is healthy.",),
            )
        return CheckResult(
            name="antivirus",
            title="Antivirus",
            status=CheckStatus.UNKNOWN,
            summary=(
                command_failure_message("Microsoft Defender status", defender_query)
                if defender_query.failure is not None
                else "Microsoft Defender status returned invalid data."
            ),
        )
    enabled = bool(status_data.get("AMServiceEnabled") and status_data.get("AntivirusEnabled"))
    real_time = bool(status_data.get("RealTimeProtectionEnabled"))
    if not enabled:
        third_party_products = _third_party_antivirus_products()
        if third_party_products:
            return CheckResult(
                name="antivirus",
                title="Antivirus",
                status=CheckStatus.UNKNOWN,
                summary="Defender is disabled and third-party antivirus was detected.",
                metrics={
                    "defender": status_data,
                    "third_party_products": list(third_party_products),
                },
                findings=("Verify the registered third-party antivirus is healthy.",),
            )
        return CheckResult(
            name="antivirus",
            title="Antivirus",
            status=CheckStatus.FAIL,
            summary="Microsoft Defender antivirus is not enabled.",
            metrics={"defender": status_data},
            findings=("Enable a supported antivirus product and verify its status.",),
            deductions=(
                ScoreDeduction(
                    "No active Microsoft Defender antivirus was detected",
                    DEFAULT_POLICY.antivirus_disabled_points,
                    "antivirus",
                ),
            ),
        )
    if not real_time:
        return CheckResult(
            name="antivirus",
            title="Antivirus",
            status=CheckStatus.WARNING,
            summary="Microsoft Defender is enabled but real-time protection is off.",
            metrics={"defender": status_data},
            findings=(
                "Turn on real-time protection or verify the approved third-party antivirus.",
            ),
            deductions=(
                ScoreDeduction(
                    "Real-time antivirus protection is disabled",
                    DEFAULT_POLICY.realtime_antivirus_disabled_points,
                    "antivirus",
                ),
            ),
        )
    signature_age = _signature_age_days(status_data.get("AntivirusSignatureLastUpdated"))
    if signature_age is not None and signature_age > DEFAULT_POLICY.stale_antivirus_signature_days:
        return CheckResult(
            name="antivirus",
            title="Antivirus",
            status=CheckStatus.WARNING,
            summary=f"Microsoft Defender signatures are {signature_age} days old.",
            metrics={"defender": status_data, "signature_age_days": signature_age},
            findings=("Update Microsoft Defender signatures.",),
            deductions=(
                ScoreDeduction(
                    "Antivirus signatures are more than 14 days old",
                    DEFAULT_POLICY.stale_antivirus_signatures_points,
                    "antivirus",
                ),
            ),
        )
    return CheckResult(
        name="antivirus",
        title="Antivirus",
        status=CheckStatus.PASS,
        summary="Microsoft Defender antivirus and real-time protection are enabled.",
        metrics={"defender": status_data, "signature_age_days": signature_age},
    )
