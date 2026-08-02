"""Rich terminal rendering for Shuri reports."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from shuri.core.comparison import ReportComparison
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


def _metric_label(key: str) -> str:
    return key.removesuffix("_bytes").replace("_", " ").title()


def show_check(result: CheckResult, console: Console | None = None) -> None:
    """Display one detailed diagnostic result."""
    target = console or _CONSOLE
    table = Table(title=result.title, show_header=True, header_style="bold bright_blue")
    table.add_column("Status", width=12)
    table.add_column("Summary")
    table.add_column("Duration", justify="right")
    table.add_row(_status_text(result.status), result.summary, f"{result.duration_ms:.0f} ms")
    target.print(table)
    if result.metrics:
        metrics = Table(show_header=True, header_style="bold")
        metrics.add_column("Metric", style="bright_blue")
        metrics.add_column("Value")
        for key, value in result.metrics.items():
            metrics.add_row(_metric_label(key), _metric_value(key, value))
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
                f"Coverage: {assessment.completed_checks}/{len(report.results)} checks "
                f"({assessment.coverage_percent:.1f}%)\n"
                f"Scan duration: {report.duration_ms / 1000:.1f}s\n"
                f"Host: {report.hostname}   •   {generated}",
                title=title,
                border_style="bright_blue",
            )
        )
    else:
        target.print(
            Panel.fit(
                f"Host: {report.hostname}\nScan duration: {report.duration_ms / 1000:.1f}s",
                title=title,
                border_style="bright_blue",
            )
        )
    table = Table(show_header=True, header_style="bold bright_blue")
    table.add_column("Check", style="bold")
    table.add_column("Status", width=12)
    table.add_column("Summary")
    table.add_column("Duration", justify="right")
    for result in report.results:
        table.add_row(
            result.title,
            _status_text(result.status),
            result.summary,
            f"{result.duration_ms:.0f} ms",
        )
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


def show_history(reports: tuple[Report, ...], console: Console | None = None) -> None:
    """Display retained reports newest first with stable selection numbers."""
    target = console or _CONSOLE
    table = Table(title="Shuri — Report History", header_style="bold bright_blue")
    table.add_column("#", justify="right")
    table.add_column("Generated")
    table.add_column("Score", justify="right")
    table.add_column("Coverage", justify="right")
    table.add_column("Host")
    table.add_column("Version")
    for index, report in enumerate(reports, start=1):
        assessment = report.assessment
        table.add_row(
            str(index),
            report.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            str(assessment.score) if assessment else "Not assessed",
            f"{assessment.coverage_percent:.1f}%" if assessment else "—",
            report.hostname,
            report.shuri_version,
        )
    target.print(table)
    target.print("[dim]Use 'shuri compare --older N --newer N' to compare assessments.[/dim]")


def show_comparison(comparison: ReportComparison, console: Console | None = None) -> None:
    """Display score, coverage, and diagnostic changes between assessments."""
    target = console or _CONSOLE
    older_assessment = comparison.older.assessment
    newer_assessment = comparison.newer.assessment
    if older_assessment is None or newer_assessment is None:  # Defensive rendering boundary.
        raise ValueError("Comparison reports must contain assessments.")
    score_sign = "+" if comparison.score_change > 0 else ""
    coverage_sign = "+" if comparison.coverage_change > 0 else ""
    target.print(
        Panel.fit(
            f"Older: {comparison.older.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')} — "
            f"{older_assessment.score}/100\n"
            f"Newer: {comparison.newer.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')} — "
            f"{newer_assessment.score}/100\n"
            f"Score change: [bold]{score_sign}{comparison.score_change}[/bold]\n"
            f"Coverage change: {coverage_sign}{comparison.coverage_change:.1f}%",
            title="Shuri — Health Comparison",
            border_style="bright_blue",
        )
    )
    if comparison.status_changes:
        table = Table(title="Diagnostic status changes", header_style="bold bright_blue")
        table.add_column("Check", style="bold")
        table.add_column("Older")
        table.add_column("Newer")
        for change in comparison.status_changes:
            table.add_row(change.title, _status_text(change.older), _status_text(change.newer))
        target.print(table)
    else:
        target.print("[green]No diagnostic statuses changed.[/green]")
    if comparison.added_checks:
        target.print(f"Added checks: {', '.join(comparison.added_checks)}")
    if comparison.removed_checks:
        target.print(f"Removed checks: {', '.join(comparison.removed_checks)}")
    if comparison.metric_changes:
        metrics = Table(title="Metric trends", header_style="bold bright_blue")
        metrics.add_column("Metric")
        metrics.add_column("Older", justify="right")
        metrics.add_column("Newer", justify="right")
        metrics.add_column("Change", justify="right")
        for metric_change in comparison.metric_changes:
            if metric_change.unit == "bytes":
                older = format_bytes(metric_change.older)
                newer = format_bytes(metric_change.newer)
                delta = format_bytes(abs(metric_change.delta))
                delta = f"{'+' if metric_change.delta > 0 else '-'}{delta}"
            else:
                suffix = metric_change.unit
                older = f"{metric_change.older:g}{suffix}"
                newer = f"{metric_change.newer:g}{suffix}"
                delta = f"{metric_change.delta:+g}{suffix}"
            metrics.add_row(metric_change.label, older, newer, delta)
        target.print(metrics)


def show_history_cleared(count: int, console: Console | None = None) -> None:
    """Confirm local history cleanup without implying the latest report was deleted."""
    (console or _CONSOLE).print(
        f"[green]Cleared {count} historical report(s).[/green] The latest report was retained."
    )


def show_error(message: str, console: Console | None = None) -> None:
    """Render an error consistently without leaking presentation into checks."""
    (console or _CONSOLE).print(f"[red]{message}[/red]")


@contextmanager
def scan_progress(
    console: Console | None = None,
) -> Iterator[Callable[[str, CheckResult | None, int, int], None]]:
    """Show one compact live progress line while diagnostics execute."""
    target = console or _CONSOLE
    progress = Progress(
        SpinnerColumn(), TextColumn("{task.description}"), console=target, transient=True
    )
    task_id = progress.add_task("Preparing diagnostics")

    def update(name: str, result: CheckResult | None, index: int, total: int) -> None:
        if result is None:
            progress.update(task_id, description=f"[{index}/{total}] Running {name}")
        else:
            duration = f"{result.duration_ms:.0f} ms"
            progress.update(
                task_id,
                description=f"[{index}/{total}] {result.title} finished in {duration}",
            )

    with progress:
        yield update
