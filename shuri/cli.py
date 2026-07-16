from __future__ import annotations

import typer

from shuri.checks.system import SystemInfoCollectionError, collect_system_info
from shuri.reporters.terminal import render_system_info

app = typer.Typer(
    name="shuri",
    help="A modern workstation diagnostics toolkit.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Run local workstation diagnostics."""


@app.command("system-info")
def system_info() -> None:
    """Show a concise snapshot of the current workstation."""
    try:
        snapshot = collect_system_info()
    except SystemInfoCollectionError as exc:
        typer.echo(f"Unable to collect system information: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    render_system_info(snapshot)
