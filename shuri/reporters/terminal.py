from __future__ import annotations

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from shuri.models.system import SystemInfo
from shuri.utils.formatting import format_bytes, format_duration


def render_system_info(info: SystemInfo, *, console: Console | None = None) -> None:
    """Render a system snapshot as a compact terminal table."""
    output = console or Console()
    table = Table(title="System Information", box=box.ROUNDED, show_header=False)
    table.add_column("Field", style="bold bright_blue", no_wrap=True)
    table.add_column("Value")

    rows = (
        ("Hostname", info.hostname),
        ("Operating system", f"{info.os_name} {info.os_release} ({info.os_version})"),
        ("Architecture", info.architecture),
        ("Processor", info.processor),
        ("CPU cores", _format_cpu_cores(info.physical_cores, info.logical_cores)),
        (
            "Memory",
            f"{format_bytes(info.memory_available_bytes)} available / "
            f"{format_bytes(info.memory_total_bytes)} total",
        ),
        (
            "Disk",
            f"{format_bytes(info.disk_free_bytes)} free / "
            f"{format_bytes(info.disk_total_bytes)} total",
        ),
        ("Uptime", format_duration(info.uptime_seconds)),
        ("Python", info.python_version),
    )

    for label, value in rows:
        table.add_row(Text(label), Text(value))

    output.print(table)


def _format_cpu_cores(physical: int | None, logical: int | None) -> str:
    physical_value = str(physical) if physical is not None else "Unknown"
    logical_value = str(logical) if logical is not None else "Unknown"
    return f"{physical_value} physical / {logical_value} logical"
