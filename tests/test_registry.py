from __future__ import annotations

import pytest

from shuri.core.exceptions import UnknownDiagnosticError
from shuri.core.registry import DiagnosticRegistry
from shuri.models import CheckResult, CheckStatus


def _healthy() -> CheckResult:
    return CheckResult("test", "Test", CheckStatus.PASS, "Healthy")


def test_registry_preserves_order_and_resolves_checks() -> None:
    registry = DiagnosticRegistry()
    registry.register("first", _healthy)
    registry.register("second", _healthy)

    assert registry.names() == ("first", "second")
    assert registry.get("first") is _healthy


def test_registry_rejects_duplicate_names() -> None:
    registry = DiagnosticRegistry()
    registry.register("test", _healthy)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("test", _healthy)


def test_registry_reports_unknown_diagnostics() -> None:
    with pytest.raises(UnknownDiagnosticError, match="missing"):
        DiagnosticRegistry().get("missing")
