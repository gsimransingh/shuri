from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO

from rich.console import Console

from shuri.models.system import SystemInfo
from shuri.reporters.terminal import render_system_info


def test_render_system_info_includes_key_values() -> None:
    snapshot = SystemInfo(
        hostname="workstation-01",
        os_name="TestOS",
        os_release="1.0",
        os_version="build-42",
        architecture="x86_64",
        processor="Test CPU",
        python_version="3.12.10",
        physical_cores=4,
        logical_cores=8,
        memory_total_bytes=16 * 1024**3,
        memory_available_bytes=8 * 1024**3,
        disk_total_bytes=500 * 1024**3,
        disk_free_bytes=125 * 1024**3,
        boot_time_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        uptime_seconds=3_661,
    )
    stream = StringIO()
    console = Console(file=stream, color_system=None, force_terminal=False, width=120)

    render_system_info(snapshot, console=console)

    output = stream.getvalue()
    assert "System Information" in output
    assert "workstation-01" in output
    assert "4 physical / 8 logical" in output
    assert "8.0 GiB available / 16.0 GiB total" in output
    assert "125.0 GiB free / 500.0 GiB total" in output
    assert "1h 1m" in output
