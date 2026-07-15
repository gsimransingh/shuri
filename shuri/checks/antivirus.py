"""Microsoft Defender status collection on Windows."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import is_windows, run_powershell


def _defender_status() -> dict[str, Any] | None:
    output = run_powershell(
        "Get-MpComputerStatus | Select-Object "
        "AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,"
        "AntivirusSignatureLastUpdated | ConvertTo-Json -Compress"
    )
    if output is None:
        return None
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _third_party_antivirus_products() -> tuple[str, ...]:
    """Return registered non-Defender antivirus products when Windows exposes them."""
    output = run_powershell(
        "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct | "
        "Select-Object DisplayName | ConvertTo-Json -Compress"
    )
    if output is None:
        return ()
    try:
        data = json.loads(output)
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
    try:
        updated = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return max(0, (datetime.now(UTC) - updated).days)


def check_antivirus() -> CheckResult:
    """Assess the available Microsoft Defender posture without altering it."""
    if not is_windows():
        return CheckResult(
            name="antivirus",
            title="Antivirus",
            status=CheckStatus.UNKNOWN,
            summary="Microsoft Defender diagnostics are only available on Windows.",
        )
    status_data = _defender_status()
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
            summary="Microsoft Defender status could not be queried.",
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
                    "No active Microsoft Defender antivirus was detected", 20, "antivirus"
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
                ScoreDeduction("Real-time antivirus protection is disabled", 10, "antivirus"),
            ),
        )
    signature_age = _signature_age_days(status_data.get("AntivirusSignatureLastUpdated"))
    if signature_age is not None and signature_age > 14:
        return CheckResult(
            name="antivirus",
            title="Antivirus",
            status=CheckStatus.WARNING,
            summary=f"Microsoft Defender signatures are {signature_age} days old.",
            metrics={"defender": status_data, "signature_age_days": signature_age},
            findings=("Update Microsoft Defender signatures.",),
            deductions=(
                ScoreDeduction("Antivirus signatures are more than 14 days old", 5, "antivirus"),
            ),
        )
    return CheckResult(
        name="antivirus",
        title="Antivirus",
        status=CheckStatus.PASS,
        summary="Microsoft Defender antivirus and real-time protection are enabled.",
        metrics={"defender": status_data, "signature_age_days": signature_age},
    )
