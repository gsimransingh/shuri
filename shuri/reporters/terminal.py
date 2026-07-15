"""Rich terminal rendering for Shuri reports."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from shuri.models import CheckResult, CheckStatus, Report
from shuri.utils.helpers import format_bytes

_CONSOLE = Console()
_STATUS_STYLES = {
    CheckStatus.PASS: "green",
    CheckStatus.WARNING: "yellow",
    CheckStatus.FAIL: "red",
    CheckStatus.UNKNOWN: "dim",
}


def _status_text(status: CheckStatus) -> Text:
    return Text(status.value.upper(), style=f"bold {_STATUS_STYLES[status]}")


def _metric_value(key: str, value: object) -> str:
    if key.endswith("_bytes") and isinstance(value, (int, float)):
        return format_bytes(value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return "Unavailable"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, default=str)
    return str(value)


def show_check(result: CheckResult, console: Console | None = None) -> None:
    """Display one detailed diagnostic result."""
    target = console or _CONSOLE
    table = Table(title=result.title, show_header=True, header_style="bold cyan")
    table.add_column("Status", width=12)
    table.add_column("Summary")
    table.add_row(_status_text(result.status), result.summary)
    target.print(table)
    if result.metrics:
        metrics = Table(show_header=True, header_style="bold")
        metrics.add_column("Metric", style="cyan")
        metrics.add_column("Value")
        for key, value in result.metrics.items():
            metrics.add_row(key.replace("_", " ").title(), _metric_value(key, value))
        target.print(metrics)
    if result.findings:
        target.print(
            Panel("\n".join(f"• {finding}" for finding in result.findings), title="Findings")
        )


def show_report(report: Report, console: Console | None = None) -> None:
    """Display a concise assessment summary and any actionable findings."""
    target = console or _CONSOLE
    title = "Shuri — Workstation Health"
    if report.assessment:
        assessment = report.assessment
        generated = report.generated_at.strftime("%Y-%m-%d %H:%M UTC")
        target.print(
            Panel.fit(
                f"[bold]{assessment.score}/100[/bold] — {assessment.label}\n"
                f"100 - {assessment.total_deductions} deduction point(s) = {assessment.score}\n"
                f"Host: {report.hostname}   •   {generated}",
                title=title,
                border_style="cyan",
            )
        )
    else:
        target.print(Panel.fit(f"Host: {report.hostname}", title=title, border_style="cyan"))
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Check", style="bold")
    table.add_column("Status", width=12)
    table.add_column("Summary")
    for result in report.results:
        table.add_row(result.title, _status_text(result.status), result.summary)
    target.print(table)
    action_items = [finding for result in report.results for finding in result.findings]
    if action_items:
        target.print(
            Panel(
                "\n".join(f"• {item}" for item in action_items),
                title="Action items",
                border_style="yellow",
            )
        )
    if report.assessment and report.assessment.deductions:
        deductions = Table(
            title=f"Health-score deductions (total: -{assessment.total_deductions})",
            header_style="bold yellow",
        )
        deductions.add_column("Points", justify="right")
        deductions.add_column("Reason")
        deductions.add_column("Check")
        for item in report.assessment.deductions:
            deductions.add_row(f"-{item.points}", item.reason, item.check)
        target.print(deductions)


def show_exported(path: Path, console: Console | None = None) -> None:
    """Confirm an exported report path."""
    (console or _CONSOLE).print(f"[green]Report written to[/green] {path}")


def show_error(message: str, console: Console | None = None) -> None:
    """Render an error consistently without leaking presentation into checks."""
    (console or _CONSOLE).print(f"[red]{message}[/red]")
