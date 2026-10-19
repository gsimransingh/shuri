"""The user-facing Typer command-line application.

``shuri`` runs the full readiness scan. ``shuri check <name>`` runs one check. The older
``doctor`` command and one-command-per-check names still work as hidden, deprecated aliases.
"""

from __future__ import annotations

import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer
from rich.console import Console

from shuri import __version__
from shuri.core import DiagnosticRunner, assess_health, default_registry
from shuri.core.exceptions import ExportError
from shuri.core.exitcodes import exit_code_for
from shuri.core.privacy import redact_report
from shuri.models import Report
from shuri.reporters import render_json
from shuri.reporters.terminal import (
    scan_progress,
    show_check,
    show_check_details,
    show_exported,
    show_hint,
    show_report,
)
from shuri.utils.files import write_report_file
from shuri.utils.helpers import default_report_path

# Static so that importing the CLI stays fast; a test keeps it in step with the registry.
CHECK_NAMES = (
    "system",
    "cpu",
    "memory",
    "disk",
    "physical_drives",
    "network",
    "battery",
    "services",
    "updates",
    "antivirus",
    "eventlogs",
)
_CHECK_ALIASES = {"drives": "physical_drives"}

app = typer.Typer(
    name="shuri",
    help=(
        "Fast, read-only readiness check for a Windows workstation.\n\n"
        "Run 'shuri' for the full check, 'shuri check <name>' for one check."
    ),
    epilog="Exit codes: 0 all passed, 1 warnings, 2 failed, 3 incomplete (missing evidence).",
    add_completion=False,
)


@dataclass
class _State:
    debug: bool = False


_STATE = _State()
_ERRORS = Console(stderr=True)

DetailsOption = Annotated[
    bool, typer.Option("--details", "-d", help="Show the detailed evidence behind each result.")
]
ProbeOption = Annotated[
    bool,
    typer.Option(
        "--probe",
        help="Also probe the network (one DNS lookup, one TCP connection). Off by default.",
    ),
]
JsonOption = Annotated[
    Path | None,
    typer.Option(
        "--json",
        metavar="PATH",
        help="Also save a JSON report to PATH. Hostname and network identifiers are redacted.",
    ),
]
RawOption = Annotated[
    bool,
    typer.Option("--raw", help="With --json: keep hostname and network identifiers (be careful)."),
]
ForceOption = Annotated[
    bool, typer.Option("--force", help="With --json: replace the file if it already exists.")
]
DebugOption = Annotated[
    bool,
    typer.Option(
        "--debug",
        help="Print tracebacks of failed diagnostics to stderr (they may contain file paths).",
    ),
]


def _print_tracebacks(runner: DiagnosticRunner) -> None:
    for name, trace in runner.tracebacks.items():
        _ERRORS.print(f"[bold red]Traceback for the '{name}' diagnostic:[/bold red]")
        sys.stderr.write(trace)


def _deprecated(instead: str) -> None:
    _ERRORS.print(f"[dim]Deprecated: use '{instead}' instead.[/dim]")


def _build_report(*, probe: bool = False) -> Report:
    registry = default_registry(probe=probe)
    started = perf_counter()
    runner = DiagnosticRunner(registry, capture_tracebacks=_STATE.debug)
    with scan_progress() as progress:
        results = runner.run(
            None,
            progress=progress,
            max_workers=4,
            serial_names=("cpu",),
        )
    _print_tracebacks(runner)
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


def _run_scan(
    *,
    details: bool,
    json_path: Path | None,
    raw: bool,
    force: bool,
    probe: bool,
    export: bool,
) -> None:
    """Run every check, show the report, optionally export it, and exit with its code."""
    report = _build_report(probe=probe)
    show_report(report, details=details)
    if export:
        show_exported(_export(report, json_path, raw=raw, force=force), raw=raw)
    else:
        show_hint()
    raise typer.Exit(int(exit_code_for(report.results)))


def _run_check(name: str, *, details: bool, probe: bool) -> None:
    runner = DiagnosticRunner(default_registry(probe=probe), capture_tracebacks=_STATE.debug)
    result = runner.run((name,))[0]
    _print_tracebacks(runner)
    show_check(result)
    if details:
        show_check_details(result)
    raise typer.Exit(int(exit_code_for((result,))))


@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    details: DetailsOption = False,
    json_path: JsonOption = None,
    raw: RawOption = False,
    force: ForceOption = False,
    probe: ProbeOption = False,
    debug: DebugOption = False,
) -> None:
    """Run the full readiness check when no command is given."""
    _STATE.debug = debug
    if ctx.invoked_subcommand is not None:
        if details or json_path or raw or force or probe:
            raise typer.BadParameter(
                "Put --details, --json, --raw, --force and --probe after the command, "
                "for example: shuri check cpu --details"
            )
        return
    if (raw or force) and json_path is None:
        raise typer.BadParameter("--raw and --force only apply together with --json PATH.")
    _run_scan(
        details=details,
        json_path=json_path,
        raw=raw,
        force=force,
        probe=probe,
        export=json_path is not None,
    )


@app.command()
def check(
    name: Annotated[str, typer.Argument(help="Which check to run.", metavar="NAME")],
    details: DetailsOption = False,
    probe: ProbeOption = False,
) -> None:
    """Run one check: system, cpu, memory, disk, physical_drives (drives), network, battery,
    services, updates, antivirus or eventlogs."""
    resolved = _CHECK_ALIASES.get(name.lower(), name.lower())
    if resolved not in CHECK_NAMES:
        valid = ", ".join([*CHECK_NAMES, *_CHECK_ALIASES])
        raise typer.BadParameter(f"'{name}' is not a check. Choose one of: {valid}.")
    _run_check(resolved, details=details, probe=probe)


@app.command()
def version() -> None:
    """Display the installed Shuri version."""
    Console().print(f"Shuri {__version__}")


# --- Deprecated aliases, kept hidden for one release ---------------------------------------------


def _validate_action(action: str | None) -> None:
    if action not in {None, "show"}:
        raise typer.BadParameter("The only supported action is 'show'.")


@app.command(name="doctor", hidden=True)
def _legacy_doctor(
    action: Annotated[str | None, typer.Argument()] = None,
    report_format: Annotated[str | None, typer.Option("--format", "-f")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    raw: RawOption = False,
    force: ForceOption = False,
    redact: Annotated[bool, typer.Option("--redact", hidden=True)] = False,
) -> None:
    """Deprecated: run 'shuri' instead."""
    _deprecated("shuri")
    _validate_action(action)
    if report_format and report_format.lower() != "json":
        raise typer.BadParameter("Format must be json.")
    if (output or raw or force or redact) and report_format is None:
        raise typer.BadParameter("--output, --raw, --redact and --force require --format json.")
    if raw and redact:
        raise typer.BadParameter("--raw and --redact cannot be combined.")
    _run_scan(
        details=action == "show",
        json_path=output,
        raw=raw,
        force=force,
        probe=False,
        export=report_format is not None,
    )


def _register_legacy_check(command: str, check_name: str) -> None:
    def legacy(action: Annotated[str | None, typer.Argument()] = None) -> None:
        _deprecated(f"shuri check {command}")
        _validate_action(action)
        _run_check(check_name, details=action == "show", probe=False)

    legacy.__doc__ = f"Deprecated: run 'shuri check {command}' instead."
    app.command(name=command, hidden=True)(legacy)


for _command, _check_name in (
    ("cpu", "cpu"),
    ("memory", "memory"),
    ("disk", "disk"),
    ("drives", "physical_drives"),
    ("network", "network"),
    ("battery", "battery"),
    ("system", "system"),
    ("services", "services"),
    ("updates", "updates"),
    ("antivirus", "antivirus"),
    ("eventlogs", "eventlogs"),
):
    _register_legacy_check(_command, _check_name)
