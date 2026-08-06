"""Opt-in, read-only integration coverage for Linux and macOS collectors."""

from __future__ import annotations

import os
import platform

import pytest

from shuri.core.registry import default_registry
from shuri.models import CheckResult


@pytest.mark.native_integration
@pytest.mark.skipif(
    platform.system() not in {"Linux", "Darwin"}
    or os.environ.get("SHURI_RUN_NATIVE_INTEGRATION") != "1",
    reason="Set SHURI_RUN_NATIVE_INTEGRATION=1 on Linux or macOS to run native checks.",
)
def test_native_collectors_complete_without_mutating_state() -> None:
    registry = default_registry()

    for name in ("services", "updates", "antivirus", "eventlogs", "physical_drives"):
        result = registry.get(name)()
        assert isinstance(result, CheckResult)
        assert result.name == name
        assert result.summary
