"""Microsoft Defender status collection on Windows."""

from __future__ import annotations

import json
from typing import Any

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import is_windows, run_command


def _defender_status() -> dict[str, Any] | None:
    output = run_command(
        (
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-MpComputerStatus | Select-Object "
            "AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,"
            "AntivirusSignatureLastUpdated | ConvertTo-Json -Compress",
        )
    )
    if output is None:
        return None
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


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
        return CheckResult(
            name="antivirus",
            title="Antivirus",
            status=CheckStatus.UNKNOWN,
            summary="Microsoft Defender status could not be queried.",
        )
    enabled = bool(status_data.get("AMServiceEnabled") and status_data.get("AntivirusEnabled"))
    real_time = bool(status_data.get("RealTimeProtectionEnabled"))
    if not enabled:
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
    return CheckResult(
        name="antivirus",
        title="Antivirus",
        status=CheckStatus.PASS,
        summary="Microsoft Defender antivirus and real-time protection are enabled.",
        metrics={"defender": status_data},
    )
