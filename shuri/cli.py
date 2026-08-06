"""The user-facing Typer command-line application."""

from __future__ import annotations

import socket
from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer

from shuri import __version__
from shuri.core import DiagnosticRunner, assess_health, compare_reports, default_registry
from shuri.core.exceptions import ReportStorageError
from shuri.core.privacy import redact_report
from shuri.core.storage import (
    clear_report_history,
    load_latest_report,
    load_report_history,
    save_latest_report,
)
from shuri.models import Report
from shuri.reporters import render_html, render_json, render_markdown
from shuri.reporters.terminal import (
    scan_progress,
    show_check,
    show_check_details,
    show_comparison,
    show_error,
    show_exported,
    show_history,
    show_history_cleared,
    show_report,
)
from shuri.utils.helpers import default_report_path

app = typer.Typer(
    name="shuri",
    help="Fast, transparent workstation health diagnostics.",
    no_args_is_help=True,
    add_completion=False,
)

OutputPath = Annotated[
    Path | None, typer.Option("--output", "-o", help="Where to write the report.")
]
ReportFormat = Annotated[
    str | None,
    typer.Option("--format", "-f", help="html, json, or markdown"),
]


def _build_report(with_assessment: bool, names: tuple[str, ...] | None = None) -> Report:
    registry = default_registry()
    started = perf_counter()
    with scan_progress() as progress:
        results = DiagnosticRunner(registry).run(
            names,
            progress=progress,
            max_workers=4,
            serial_names=("cpu",),
        )
    scan_duration_ms = (perf_counter() - started) * 1000
    assessment = assess_health(results) if with_assessment else None
    report = Report.create(
        results=results,
        hostname=socket.gethostname(),
        assessment=assessment,
        scan_duration_ms=round(scan_duration_ms, 1),
    )
    try:
        save_latest_report(report)
    except ReportStorageError as error:
        show_error(str(error))
        raise typer.Exit(code=1) from error
    return report


def _selected_format(
    report_format: str | None, html: bool, json_format: bool, markdown: bool
) -> str | None:
    selected = [report_format.lower()] if report_format else []
    selected.extend(
        name
        for name, enabled in (("html", html), ("json", json_format), ("markdown", markdown))
        if enabled
    )
    if len(selected) > 1:
        raise typer.BadParameter(
            "Choose one format option: -f/--format, --html, --json, or --markdown."
        )
    if selected and selected[0] not in {"html", "json", "markdown"}:
        raise typer.BadParameter("Format must be html, json, or markdown.")
    return selected[0] if selected else None


def _render(report: Report, report_format: str) -> str:
    renderers = {"html": render_html, "json": render_json, "markdown": render_markdown}
    try:
        return renderers[report_format](report)
    except KeyError as error:
        valid = ", ".join(renderers)
        raise typer.BadParameter(
            f"Unsupported format '{report_format}'. Choose: {valid}."
        ) from error


def _export(
    report: Report, report_format: str, output: Path | None, *, redact: bool = False
) -> Path:
    path = output or default_report_path(report_format)
    path.parent.mkdir(parents=True, exist_ok=True)
    exported_report = redact_report(report) if redact else report
    path.write_text(_render(exported_report, report_format), encoding="utf-8")
    return path


@app.command()
def scan() -> None:
    """Run every supported diagnostic and display a concise result summary."""
    report = _build_report(with_assessment=False)
    show_report(report)


@app.command()
def doctor(
    action: Annotated[str | None, typer.Argument(help="Use 'show' for detailed evidence.")] = None,
    report_format: ReportFormat = None,
    html: Annotated[bool, typer.Option("--html", help="Export an HTML report.")] = False,
    json_format: Annotated[bool, typer.Option("--json", help="Export a JSON report.")] = False,
    markdown: Annotated[bool, typer.Option("--markdown", help="Export a Markdown report.")] = False,
    output: OutputPath = None,
    redact: Annotated[
        bool,
        typer.Option("--redact", help="Remove workstation and network identifiers from export."),
    ] = False,
) -> None:
    """Run all diagnostics, calculate health, and optionally export a report."""
    _validate_action(action)
    report_format = _selected_format(report_format, html, json_format, markdown)
    if output and report_format is None:
        raise typer.BadParameter("--output requires -f/--format, --html, --json, or --markdown.")
    if redact and report_format is None:
        raise typer.BadParameter("--redact requires an exported report format.")
    report = _build_report(with_assessment=True)
    show_report(report, details=action == "show")
    if report_format:
        show_exported(_export(report, report_format, output, redact=redact))


@app.command()
def report(
    report_format: Annotated[
        str, typer.Option("--format", "-f", help="html, json, or markdown")
    ] = "json",
    output: OutputPath = None,
    redact: Annotated[
        bool,
        typer.Option("--redact", help="Remove workstation and network identifiers from export."),
    ] = False,
) -> None:
    """Export the most recently saved Shuri assessment."""
    try:
        saved = load_latest_report()
    except ReportStorageError as error:
        show_error(str(error))
        raise typer.Exit(code=1) from error
    if saved is None:
        show_error("No saved report exists. Run 'shuri doctor' or 'shuri scan' first.")
        raise typer.Exit(code=1)
    show_exported(_export(saved, report_format.lower(), output, redact=redact))


@app.command()
def history(
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, max=50)] = 10,
    clear: Annotated[bool, typer.Option("--clear", help="Delete retained report history.")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Confirm history deletion.")] = False,
) -> None:
    """List retained local reports or clear report history."""
    if yes and not clear:
        raise typer.BadParameter("--yes can only be used with --clear.")
    if clear:
        if not yes:
            raise typer.BadParameter("History deletion requires --clear --yes.")
        try:
            show_history_cleared(clear_report_history())
        except ReportStorageError as error:
            show_error(str(error))
            raise typer.Exit(code=1) from error
        return
    reports = load_report_history(limit=limit, assessed_only=True)
    if not reports:
        show_error("No report history exists. Run 'shuri doctor' to create an assessment.")
        raise typer.Exit(code=1)
    show_history(reports)


@app.command()
def compare(
    older: Annotated[
        int, typer.Option("--older", min=2, help="Older assessment number from history.")
    ] = 2,
    newer: Annotated[
        int, typer.Option("--newer", min=1, help="Newer assessment number from history.")
    ] = 1,
) -> None:
    """Compare two retained health assessments."""
    if older <= newer:
        raise typer.BadParameter("--older must be a larger history number than --newer.")
    reports = load_report_history(limit=older, assessed_only=True)
    if len(reports) < older:
        show_error(
            f"Only {len(reports)} assessed historical report(s) exist; "
            f"comparison requires assessment #{older}."
        )
        raise typer.Exit(code=1)
    show_comparison(compare_reports(reports[older - 1], reports[newer - 1]))


def _validate_action(action: str | None) -> None:
    if action not in {None, "show"}:
        raise typer.BadParameter("The only supported action is 'show'.")


def _single_check(name: str, action: str | None = None) -> None:
    _validate_action(action)
    result = DiagnosticRunner(default_registry()).run((name,))[0]
    show_check(result)
    if action == "show":
        show_check_details(result)


def _run_single_command(name: str, action: str | None) -> None:
    """Preserve the original one-argument command boundary for concise commands."""
    if action is None:
        _single_check(name)
    else:
        _single_check(name, action)


@app.command()
def cpu(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run CPU diagnostics only."""
    _run_single_command("cpu", action)


@app.command()
def memory(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run memory diagnostics only."""
    _run_single_command("memory", action)


@app.command()
def disk(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run disk diagnostics only."""
    _run_single_command("disk", action)


@app.command(name="drives")
def physical_drives(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run physical-drive reliability diagnostics only."""
    _run_single_command("physical_drives", action)


@app.command()
def network(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run network diagnostics only."""
    _run_single_command("network", action)


@app.command()
def battery(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run battery diagnostics only."""
    _run_single_command("battery", action)


@app.command()
def system(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run operating-system diagnostics only."""
    _run_single_command("system", action)


@app.command(name="system-info")
def system_info(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Show operating-system and workstation information."""
    _run_single_command("system", action)


@app.command()
def services(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run native system-service diagnostics only."""
    _run_single_command("services", action)


@app.command()
def updates(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run native system-update diagnostics only."""
    _run_single_command("updates", action)


@app.command()
def antivirus(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run native security-posture diagnostics only."""
    _run_single_command("antivirus", action)


@app.command(name="eventlogs")
def event_logs(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run recent native system-log diagnostics only."""
    _run_single_command("eventlogs", action)


@app.command()
def version() -> None:
    """Display the installed Shuri version."""
    from rich.console import Console

    Console().print(f"Shuri {__version__}")


if __name__ == "__main__":
    app()
