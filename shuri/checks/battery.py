"""Laptop battery diagnostics when the operating system exposes them."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from uuid import uuid4

import psutil

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import is_windows, run_command

_CRITICAL_HEALTH_PERCENT = 60.0
_LOW_HEALTH_PERCENT = 80.0


def parse_battery_report(report: str) -> tuple[int | None, int | None]:
    """Extract design and full-charge capacities in mWh from a battery report."""
    return _capacity_from_report(report, "DESIGN CAPACITY"), _capacity_from_report(
        report, "FULL CHARGE CAPACITY"
    )


def _capacity_from_report(report: str, label: str) -> int | None:
    match = re.search(rf"{label}.*?([0-9][0-9,]*)\s*mWh", report, flags=re.IGNORECASE | re.DOTALL)
    return int(match.group(1).replace(",", "")) if match else None


def _battery_health() -> tuple[int | None, int | None, float | None]:
    """Return Windows battery design capacity, full-charge capacity, and health percentage."""
    if not is_windows():
        return None, None, None
    report_path = Path(tempfile.gettempdir()) / f"shuri-battery-{uuid4().hex}.html"
    try:
        result = run_command(
            ("powercfg", "/batteryreport", "/output", str(report_path)), timeout=10
        )
        if result is None or not report_path.is_file():
            return None, None, None
        design_capacity, full_charge_capacity = parse_battery_report(
            report_path.read_text(encoding="utf-8", errors="replace")
        )
    finally:
        report_path.unlink(missing_ok=True)
    if not design_capacity or full_charge_capacity is None:
        return design_capacity, full_charge_capacity, None
    return (
        design_capacity,
        full_charge_capacity,
        round(full_charge_capacity / design_capacity * 100, 1),
    )


def check_battery() -> CheckResult:
    """Collect current battery state and Windows capacity health where available."""
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
    design_capacity, full_charge_capacity, health_percent = _battery_health()
    if health_percent is not None and health_percent < _CRITICAL_HEALTH_PERCENT:
        status = CheckStatus.FAIL
        findings.append("Battery full-charge capacity is below 60% of its design capacity.")
        deductions.append(ScoreDeduction("Battery health is below 60%", 5, "battery"))
    elif health_percent is not None and health_percent < _LOW_HEALTH_PERCENT:
        status = CheckStatus.WARNING if status is CheckStatus.PASS else status
        findings.append("Battery full-charge capacity is below 80% of its design capacity.")
        deductions.append(ScoreDeduction("Battery health is below 80%", 3, "battery"))
    power_state = "charging" if battery.power_plugged else "on battery"
    health_summary = (
        f" Estimated capacity health is {health_percent:.0f}%."
        if health_percent is not None
        else " Capacity health is unavailable."
    )
    return CheckResult(
        name="battery",
        title="Battery",
        status=status,
        summary=f"Battery is {battery.percent:.0f}% and {power_state}.{health_summary}",
        metrics={
            "charge_percent": battery.percent,
            "power_plugged": battery.power_plugged,
            "seconds_left": battery.secsleft if battery.secsleft >= 0 else None,
            "design_capacity_mwh": design_capacity,
            "full_charge_capacity_mwh": full_charge_capacity,
            "battery_health_percent": health_percent,
        },
        findings=tuple(findings),
        deductions=tuple(deductions),
    )
