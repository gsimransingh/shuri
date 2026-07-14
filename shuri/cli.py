"""The user-facing Typer command-line application."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Annotated

import typer

from shuri import __version__
from shuri.core import DiagnosticRunner, assess_health, default_registry
from shuri.core.storage import load_latest_report, save_latest_report
from shuri.models import Report
from shuri.reporters import render_html, render_json, render_markdown
from shuri.reporters.terminal import show_check, show_error, show_exported, show_report
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


def _build_report(with_assessment: bool, names: tuple[str, ...] | None = None) -> Report:
    results = DiagnosticRunner(default_registry()).run(names)
    assessment = assess_health(results) if with_assessment else None
    report = Report.create(results=results, hostname=socket.gethostname(), assessment=assessment)
    save_latest_report(report)
    return report


def _selected_format(html: bool, json_format: bool, markdown: bool) -> str | None:
    selected = [
        name
        for name, enabled in (("html", html), ("json", json_format), ("markdown", markdown))
        if enabled
    ]
    if len(selected) > 1:
        raise typer.BadParameter("Choose only one of --html, --json, or --markdown.")
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


def _export(report: Report, report_format: str, output: Path | None) -> Path:
    path = output or default_report_path(report_format)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(report, report_format), encoding="utf-8")
    return path


@app.command()
def scan() -> None:
    """Run every supported diagnostic and display a concise result summary."""
    report = _build_report(with_assessment=False)
    show_report(report)


@app.command()
def doctor(
    html: Annotated[bool, typer.Option("--html", help="Export an HTML report.")] = False,
    json_format: Annotated[bool, typer.Option("--json", help="Export a JSON report.")] = False,
    markdown: Annotated[bool, typer.Option("--markdown", help="Export a Markdown report.")] = False,
    output: OutputPath = None,
) -> None:
    """Run all diagnostics, calculate health, and optionally export a report."""
    report_format = _selected_format(html, json_format, markdown)
    if output and report_format is None:
        raise typer.BadParameter("--output requires --html, --json, or --markdown.")
    report = _build_report(with_assessment=True)
    show_report(report)
    if report_format:
        show_exported(_export(report, report_format, output))


@app.command()
def report(
    report_format: Annotated[
        str, typer.Option("--format", "-f", help="html, json, or markdown")
    ] = "json",
    output: OutputPath = None,
) -> None:
    """Export the most recently saved Shuri assessment."""
    saved = load_latest_report()
    if saved is None:
        show_error("No saved report exists. Run 'shuri doctor' or 'shuri scan' first.")
        raise typer.Exit(code=1)
    show_exported(_export(saved, report_format.lower(), output))


def _single_check(name: str) -> None:
    result = DiagnosticRunner(default_registry()).run((name,))[0]
    show_check(result)


@app.command()
def cpu() -> None:
    """Run CPU diagnostics only."""
    _single_check("cpu")


@app.command()
def memory() -> None:
    """Run memory diagnostics only."""
    _single_check("memory")


@app.command()
def disk() -> None:
    """Run disk diagnostics only."""
    _single_check("disk")


@app.command()
def network() -> None:
    """Run network diagnostics only."""
    _single_check("network")


@app.command()
def battery() -> None:
    """Run battery diagnostics only."""
    _single_check("battery")


@app.command()
def system() -> None:
    """Run operating-system diagnostics only."""
    _single_check("system")


@app.command()
def services() -> None:
    """Run Windows service diagnostics only."""
    _single_check("services")


@app.command()
def updates() -> None:
    """Run Windows update diagnostics only."""
    _single_check("updates")


@app.command()
def antivirus() -> None:
    """Run Microsoft Defender diagnostics only."""
    _single_check("antivirus")


@app.command(name="eventlogs")
def event_logs() -> None:
    """Run recent Windows event-log diagnostics only."""
    _single_check("eventlogs")


@app.command()
def version() -> None:
    """Display the installed Shuri version."""
    from rich.console import Console

    Console().print(f"Shuri {__version__}")


if __name__ == "__main__":
    app()
