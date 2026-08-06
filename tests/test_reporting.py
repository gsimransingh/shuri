from __future__ import annotations

from rich.console import Console

from shuri.core.scoring import assess_health
from shuri.models import CheckResult, CheckStatus, Report, ScoreDeduction
from shuri.reporters import render_json
from shuri.reporters.terminal import show_check_details, show_report


def test_json_report_is_machine_readable() -> None:
    report = Report.create(
        (CheckResult("cpu", "CPU", CheckStatus.PASS, "CPU utilisation is normal."),),
        "workstation-01",
    )

    rendered = render_json(report)

    assert '"hostname": "workstation-01"' in rendered
    assert '"status": "pass"' in rendered


def test_terminal_report_shows_score_calculation() -> None:
    result = CheckResult(
        "disk",
        "Disk",
        CheckStatus.WARNING,
        "Disk is low.",
        deductions=(ScoreDeduction("System drive is below 15% free", 8, "disk"),),
    )
    report = Report.create((result,), "workstation-01", assess_health((result,)))
    console = Console(record=True, width=120, color_system=None)

    show_report(report, console)

    assert "100 - 8 deduction point(s) = 92" in console.export_text()


def test_terminal_details_render_service_rows() -> None:
    result = CheckResult(
        "services",
        "Windows Services",
        CheckStatus.PASS,
        "Healthy.",
        metrics={
            "services": {"eventlog": {"display_name": "Windows Event Log", "state": "running"}}
        },
    )
    console = Console(record=True, width=120, color_system=None)

    show_check_details(result, console)

    rendered = console.export_text()
    assert "System Services" in rendered
    assert "Windows Event Log" in rendered
