"""The explicit registry of diagnostics included in a standard scan."""

from __future__ import annotations

from collections.abc import Callable, Iterator

from shuri.core.exceptions import UnknownDiagnosticError
from shuri.models import CheckResult

Diagnostic = Callable[[], CheckResult]


class DiagnosticRegistry:
    """An ordered, duplicate-safe collection of named diagnostics."""

    def __init__(self) -> None:
        self._checks: dict[str, Diagnostic] = {}

    def register(self, name: str, diagnostic: Diagnostic) -> None:
        """Add a diagnostic under the CLI-safe ``name``."""
        if name in self._checks:
            raise ValueError(f"Diagnostic already registered: {name}")
        self._checks[name] = diagnostic

    def get(self, name: str) -> Diagnostic:
        """Return one diagnostic or raise an informative domain error."""
        try:
            return self._checks[name]
        except KeyError as error:
            raise UnknownDiagnosticError(f"Unknown diagnostic: {name}") from error

    def names(self) -> tuple[str, ...]:
        """Return registered names in scan order."""
        return tuple(self._checks)

    def __iter__(self) -> Iterator[tuple[str, Diagnostic]]:
        return iter(self._checks.items())


def default_registry() -> DiagnosticRegistry:
    """Build the diagnostics available in Shuri's initial release."""
    from shuri.checks.antivirus import check_antivirus
    from shuri.checks.battery import check_battery
    from shuri.checks.cpu import check_cpu
    from shuri.checks.disk import check_disk
    from shuri.checks.eventlogs import check_event_logs
    from shuri.checks.memory import check_memory
    from shuri.checks.network import check_network
    from shuri.checks.services import check_services
    from shuri.checks.system import check_system
    from shuri.checks.updates import check_updates

    registry = DiagnosticRegistry()
    for name, check in (
        ("system", check_system),
        ("cpu", check_cpu),
        ("memory", check_memory),
        ("disk", check_disk),
        ("network", check_network),
        ("battery", check_battery),
        ("services", check_services),
        ("updates", check_updates),
        ("antivirus", check_antivirus),
        ("eventlogs", check_event_logs),
    ):
        registry.register(name, check)
    return registry
