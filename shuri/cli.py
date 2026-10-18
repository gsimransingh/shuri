"""The user-facing Typer command-line application."""

from __future__ import annotations

import socket
from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer

from shuri import __version__
from shuri.core import DiagnosticRunner, assess_health, default_registry
from shuri.core.exceptions import ExportError
from shuri.core.privacy import redact_report
from shuri.models import Report
from shuri.reporters import render_json
from shuri.reporters.terminal import (
    scan_progress,
    show_check,
    show_check_details,
    show_exported,
    show_report,
)
from shuri.utils.files import write_report_file
from shuri.utils.helpers import default_report_path

app = typer.Typer(
    name="shuri",
    help="Fast, transparent Windows workstation-readiness diagnostics.",
    no_args_is_help=True,
    add_completion=False,
)

OutputPath = Annotated[
    Path | None, typer.Option("--output", "-o", help="Where to write the JSON report.")
]
ReportFormat = Annotated[str | None, typer.Option("--format", "-f", help="json")]


def _build_report(names: tuple[str, ...] | None = None) -> Report:
    registry = default_registry()
    started = perf_counter()
    with scan_progress() as progress:
        results = DiagnosticRunner(registry).run(
            names,
            progress=progress,
            max_workers=4,
            serial_names=("cpu",),
        )
    return Report.create(
        results=results,
        hostname=socket.gethostname(),
        assessment=assess_health(results),
        scan_duration_ms=round((perf_counter() - started) * 1000, 1),
    )


def _export(report: Report, output: Path | None, *, raw: bool = False, force: bool = False) -> Path:
    path = output or default_report_path("json")
    exported_report = report if raw else redact_report(report)
    try:
        return write_report_file(path, render_json(exported_report), overwrite=force)
    except ExportError as error:
        raise typer.BadParameter(str(error)) from None


def _validate_action(action: str | None) -> None:
    if action not in {None, "show"}:
        raise typer.BadParameter("The only supported action is 'show'.")


@app.command()
def doctor(
    action: Annotated[str | None, typer.Argument(help="Use 'show' for detailed evidence.")] = None,
    report_format: ReportFormat = None,
    output: OutputPath = None,
    raw: Annotated[
        bool,
        typer.Option(
            "--raw",
            help="Keep hostname and network identifiers in the JSON export (redacted by default).",
        ),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Replace the export file if it already exists.")
    ] = False,
    redact: Annotated[
        bool,
        typer.Option("--redact", hidden=True, help="Deprecated: exports are redacted by default."),
    ] = False,
) -> None:
    """Run the Windows workstation-readiness assessment."""
    _validate_action(action)
    if report_format and report_format.lower() != "json":
        raise typer.BadParameter("Format must be json.")
    if (output or raw or force or redact) and report_format is None:
        raise typer.BadParameter("--output, --raw, --redact and --force require --format json.")
    if raw and redact:
        raise typer.BadParameter("--raw and --redact cannot be combined.")
    report = _build_report()
    show_report(report, details=action == "show")
    if report_format:
        show_exported(_export(report, output, raw=raw, force=force), raw=raw)


def _single_check(name: str, action: str | None = None) -> None:
    _validate_action(action)
    result = DiagnosticRunner(default_registry()).run((name,))[0]
    show_check(result)
    if action == "show":
        show_check_details(result)


def _run_single_command(name: str, action: str | None) -> None:
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


@app.command()
def services(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run Windows service diagnostics only."""
    _run_single_command("services", action)


@app.command()
def updates(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run Windows update diagnostics only."""
    _run_single_command("updates", action)


@app.command()
def antivirus(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run Microsoft Defender diagnostics only."""
    _run_single_command("antivirus", action)


@app.command(name="eventlogs")
def event_logs(action: Annotated[str | None, typer.Argument()] = None) -> None:
    """Run recent Windows event-log diagnostics only."""
    _run_single_command("eventlogs", action)


@app.command()
def version() -> None:
    """Display the installed Shuri version."""
    from rich.console import Console

    Console().print(f"Shuri {__version__}")
