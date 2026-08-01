from __future__ import annotations

import subprocess

import pytest

from shuri.utils import platform
from shuri.utils.platform import CommandFailure


def test_command_timeout_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    def time_out(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("safe-command", 1)

    monkeypatch.setattr(platform.subprocess, "run", time_out)

    result = platform.run_command(("safe-command",), timeout=1)

    assert result.failure is CommandFailure.TIMEOUT
    assert "timed out" in platform.command_failure_message("Diagnostic", result)


def test_nonzero_exit_does_not_expose_raw_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = subprocess.CompletedProcess(
        args=("safe-command",), returncode=17, stdout="", stderr="secret internal detail"
    )
    monkeypatch.setattr(platform.subprocess, "run", lambda *args, **kwargs: completed)

    result = platform.run_command(("safe-command",))
    message = platform.command_failure_message("Diagnostic", result)

    assert result.failure is CommandFailure.EXIT_CODE
    assert result.exit_code == 17
    assert "secret" not in message
