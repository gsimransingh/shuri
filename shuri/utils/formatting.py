from __future__ import annotations


def format_bytes(value: int) -> str:
    """Format a non-negative byte count using binary units."""
    if value < 0:
        raise ValueError("value must not be negative")

    size = float(value)
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
    for unit in units[:-1]:
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024

    return f"{size:.1f} {units[-1]}"


def format_duration(total_seconds: int) -> str:
    """Format a non-negative duration as a compact human-readable value."""
    if total_seconds < 0:
        raise ValueError("total_seconds must not be negative")

    days, remainder = divmod(total_seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)
