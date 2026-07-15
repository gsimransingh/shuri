"""Network-specific data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdapterSnapshot:
    """A network adapter's support-relevant identity and state."""

    name: str
    is_up: bool
    addresses: tuple[str, ...]
    mac_address: str | None = None
