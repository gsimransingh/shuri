"""Network-specific data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdapterSnapshot:
    """A network adapter's minimal support-relevant data."""

    name: str
    is_up: bool
    addresses: tuple[str, ...]
