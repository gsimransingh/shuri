"""Formatting and serialisation helpers."""

from __future__ import annotations

from pathlib import Path


def format_bytes(value: int | float | None) -> str:
    """Render a byte count in a compact binary unit."""
    if value is None:
        return "Unavailable"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(size) < 1024 or unit == "PiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size:.0f} B"
        size /= 1024
    return f"{size:.1f} PiB"


def default_report_path(extension: str) -> Path:
    """Return a predictable report name in the current working directory."""
    return Path.cwd() / f"shuri-report.{extension.lstrip('.')}"
