"""Rich terminal rendering for Shuri reports."""

from __future__ import annotations

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
    if isinstance(value, dict):
        succeeded = value.get("succeeded")
        if isinstance(succeeded, bool):
            return "Working" if succeeded else "Not working"
        if key == "process_attribution":
            contributors = value.get("contributors")
            count = len(contributors) if isinstance(contributors, list) else 0
            resource = str(value.get("resource", "resource")).upper()
            state = str(value.get("state", "unavailable")).title()
            return f"{count} {resource} contributor(s) captured ({state})"
        if key == "services":
            running = sum(
                1
                for service in value.values()
                if (service.get("state") if isinstance(service, dict) else service) == "running"
            )
            return f"{running} running of {len(value)} monitored"
        if key == "defender":
            enabled = bool(value.get("AMServiceEnabled") and value.get("AntivirusEnabled"))
            real_time = bool(value.get("RealTimeProtectionEnabled"))
            if enabled:
                return "Enabled; real-time protection " + ("on" if real_time else "off")
            return "Disabled"
        return f"{len(value)} detail(s) available"
    if isinstance(value, (list, tuple)):
        if not value:
            return "None"
        if key == "dns_servers":
            return f"{len(value)} configured"
        if key == "recent_events":
            return f"{len(value)} recorded"
        if all(isinstance(item, (str, int, float, bool)) for item in value):
            visible = ", ".join(str(item) for item in value[:3])
            remaining = len(value) - 3
            return f"{visible} (+{remaining} more)" if remaining else visible
        if key == "adapters":
            active = sum(
                1 for item in value if isinstance(item, dict) and item.get("is_up") is True
            )
            return f"{active} active of {len(value)} detected"
        if key == "physical_drives":
            healthy = sum(
                1
                for item in value
                if isinstance(item, dict)
                and str(item.get("health_status", "")).casefold() == "healthy"
            )
            return f"{healthy} healthy of {len(value)} detected"
        if key == "filesystems":
            return f"{len(value)} detected"
        return f"{len(value)} item(s) available"
    return str(value)


def _metric_label(key: str) -> str:
    words = key.removesuffix("_bytes").split("_")
    acronyms = {"cpu", "dns", "ip", "mac", "tcp", "usb"}
    return " ".join(word.upper() if word in acronyms else word.title() for word in words)


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


def _detail_text(value: object) -> str:
    return _metric_value("", value)


def _show_mapping_table(target: Console, title: str, entries: dict[object, object]) -> None:
    table = Table(title=title, header_style="bold bright_blue")
    table.add_column("Setting")
    table.add_column("Value")
    for key, value in entries.items():
        table.add_row(_metric_label(str(key)), _detail_text(value))
    target.print(table)


def _show_list_table(target: Console, key: str, entries: list[object]) -> bool:
    dictionaries = [entry for entry in entries if isinstance(entry, dict)]
    if not dictionaries:
        return False
    specifications = {
        "adapters": (
            "Network Adapters",
            (("name", "Adapter"), ("is_up", "State"), ("addresses", "Addresses")),
        ),
        "filesystems": (
            "Filesystems",
            (
                ("device", "Device"),
                ("mountpoint", "Mount"),
                ("filesystem", "Type"),
                ("total_bytes", "Total"),
                ("free_bytes", "Free"),
                ("used_percent", "Used %"),
            ),
        ),
        "physical_drives": (
            "Physical Drives",
            (
                ("model", "Model"),
                ("media_type", "Type"),
                ("bus_type", "Bus"),
                ("size_bytes", "Size"),
                ("health_status", "Health"),
                ("operational_status", "Operational"),
                ("temperature_celsius", "Temp °C"),
                ("wear_percent", "Wear %"),
            ),
        ),
        "recent_events": (
            "Recent System Events",
            (
                ("time_created", "Time"),
                ("level", "Level"),
                ("event_id", "Event ID"),
                ("provider", "Provider"),
            ),
        ),
    }
    specification = specifications.get(key)
    if specification is None:
        return False
    title, columns = specification
    table = Table(title=title, header_style="bold bright_blue")
    for _, label in columns:
        table.add_column(label)
    for entry in dictionaries:
        values: list[str] = []
        for field, _ in columns:
            value = entry.get(field)
            if field == "is_up":
                values.append("Connected" if value is True else "Disconnected")
            elif field.endswith("_bytes") and isinstance(value, (int, float)):
                values.append(format_bytes(value))
            elif isinstance(value, list):
                values.append(", ".join(str(item) for item in value) or "—")
            else:
                values.append("Unavailable" if value is None else str(value))
        table.add_row(*values)
    target.print(table)
    return True


def _show_process_attribution(target: Console, attribution: dict[object, object]) -> None:
    resource = str(attribution.get("resource", "resource"))
    state = str(attribution.get("state", "unavailable")).title()
    table = Table(
        title=f"Top {resource.upper()} Contributors — {state}",
        header_style="bold bright_blue",
    )
    table.add_column("Process")
    table.add_column("PID", justify="right")
    if resource == "cpu":
        table.add_column("CPU %", justify="right")
    else:
        table.add_column("Memory", justify="right")
        table.add_column("Share %", justify="right")
    contributors = attribution.get("contributors")
    if isinstance(contributors, list):
        for contributor in contributors:
            if not isinstance(contributor, dict):
                continue
            values = [
                str(contributor.get("process_name", "Unavailable")),
                str(contributor.get("process_id", "Unavailable")),
            ]
            if resource == "cpu":
                values.append(str(contributor.get("cpu_percent", "Unavailable")))
            else:
                memory_bytes = contributor.get("memory_bytes")
                values.extend(
                    (
                        (
                            format_bytes(memory_bytes)
                            if isinstance(memory_bytes, (int, float))
                            else "Unavailable"
                        ),
                        str(contributor.get("memory_percent", "Unavailable")),
                    )
                )
            table.add_row(*values)
    target.print(table)


def show_check_details(result: CheckResult, console: Console | None = None) -> None:
    """Display collected structured evidence as readable, purpose-built tables."""
    target = console or _CONSOLE
    rendered = False
    for key, value in result.metrics.items():
        if isinstance(value, list) and _show_list_table(target, key, value):
            rendered = True
        elif key == "services" and isinstance(value, dict):
            services = Table(title="System Services", header_style="bold bright_blue")
            services.add_column("Service")
            services.add_column("State")
            for service_name, service in value.items():
                if isinstance(service, dict):
                    services.add_row(
                        str(service.get("display_name", service_name)),
                        str(service.get("state", "Unavailable")).title(),
                    )
                else:
                    services.add_row(str(service_name), str(service).title())
            target.print(services)
            rendered = True
        elif key == "defender" and isinstance(value, dict):
            _show_mapping_table(target, "Microsoft Defender", value)
            rendered = True
        elif key == "security_controls" and isinstance(value, dict):
            controls = Table(title="Native Security Controls", header_style="bold bright_blue")
            controls.add_column("Control")
            controls.add_column("State")
            for control, evidence in value.items():
                state = (
                    evidence[0] if isinstance(evidence, (list, tuple)) and evidence else evidence
                )
                controls.add_row(_metric_label(str(control)), str(state).title())
            target.print(controls)
            rendered = True
        elif key in {"dns_probe", "tcp_probe"} and isinstance(value, dict):
            _show_mapping_table(target, _metric_label(key), value)
            rendered = True
        elif key == "process_attribution" and isinstance(value, dict):
            _show_process_attribution(target, value)
            rendered = True
    if not rendered:
        target.print("[dim]No additional structured evidence is available for this check.[/dim]")


def show_report(report: Report, console: Console | None = None, *, details: bool = False) -> None:
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
    if details:
        for result in report.results:
            if any(isinstance(value, (dict, list)) for value in result.metrics.values()):
                show_check_details(result, target)


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
            progress.update(task_id, description=f"Starting {name} ({index}/{total})")
        else:
            duration = f"{result.duration_ms:.0f} ms"
            progress.update(
                task_id,
                description=f"[{index}/{total}] {result.title} finished in {duration}",
            )

    with progress:
        yield update
