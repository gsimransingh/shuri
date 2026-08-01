from __future__ import annotations

import os
import platform

import pytest

from shuri.utils.platform import run_powershell

pytestmark = [
    pytest.mark.windows_integration,
    pytest.mark.skipif(
        platform.system() != "Windows" or os.environ.get("SHURI_RUN_WINDOWS_INTEGRATION") != "1",
        reason="Set SHURI_RUN_WINDOWS_INTEGRATION=1 on Windows to run safe native checks.",
    ),
]


def test_read_only_powershell_boundary_on_windows() -> None:
    result = run_powershell("$PSVersionTable.PSVersion.ToString()")

    assert result.succeeded
    assert result.output.strip()
