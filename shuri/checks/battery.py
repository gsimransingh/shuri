"""Laptop battery diagnostics when the operating system exposes them."""

from __future__ import annotations

import psutil

from shuri.models import CheckResult, CheckStatus, ScoreDeduction


def check_battery() -> CheckResult:
    """Collect current battery charge and estimated remaining runtime."""
    battery = psutil.sensors_battery()
    if battery is None:
        return CheckResult(
            name="battery",
            title="Battery",
            status=CheckStatus.UNKNOWN,
            summary="No battery information is available on this device.",
        )
    deductions: list[ScoreDeduction] = []
    findings: list[str] = []
    status = CheckStatus.PASS
    if battery.percent < 10 and not battery.power_plugged:
        status = CheckStatus.WARNING
        findings.append("Battery charge is below 10% and the device is not charging.")
        deductions.append(ScoreDeduction("Battery charge is below 10%", 3, "battery"))
    power_state = "charging" if battery.power_plugged else "on battery"
    return CheckResult(
        name="battery",
        title="Battery",
        status=status,
        summary=f"Battery is {battery.percent:.0f}% and {power_state}.",
        metrics={
            "charge_percent": battery.percent,
            "power_plugged": battery.power_plugged,
            "seconds_left": battery.secsleft if battery.secsleft >= 0 else None,
        },
        findings=tuple(findings),
        deductions=tuple(deductions),
    )
