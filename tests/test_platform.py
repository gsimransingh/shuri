from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shuri.utils import platform
from shuri.utils.platform import CommandFailure


def test_command_timeout_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    def time_out(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("safe-command", 1)

    monkeypatch.setattr(platform.subprocess, "run", time_out)

    result = platform.run_command(("sc",), timeout=1)

    assert result.failure is CommandFailure.TIMEOUT
    assert "timed out" in platform.command_failure_message("Diagnostic", result)


def test_nonzero_exit_does_not_expose_raw_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = subprocess.CompletedProcess(
        args=("safe-command",), returncode=17, stdout="", stderr="secret internal detail"
    )
    monkeypatch.setattr(platform.subprocess, "run", lambda *args, **kwargs: completed)

    result = platform.run_command(("sc",))
    message = platform.command_failure_message("Diagnostic", result)

    assert result.failure is CommandFailure.EXIT_CODE
    assert result.exit_code == 17
    assert "secret" not in message


def _pretend_windows(monkeypatch: pytest.MonkeyPatch, system_root: Path) -> None:
    monkeypatch.setattr(platform, "is_windows", lambda: True)
    monkeypatch.setenv("SYSTEMROOT", str(system_root))


def test_windows_tools_run_from_the_system_directory_not_the_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    decoy = tmp_path / "powershell.exe"
    decoy.write_text("not a real program", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _pretend_windows(monkeypatch, tmp_path / "Windows")
    captured: dict[str, object] = {}

    def fake_run(command: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(platform.subprocess, "run", fake_run)

    result = platform.run_powershell("$PSVersionTable")

    system32 = tmp_path / "Windows" / "System32"
    command = captured["command"]
    assert isinstance(command, tuple)
    assert Path(command[0]) == system32 / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    assert Path(command[0]).is_absolute()
    assert Path(str(captured["cwd"])) == system32
    assert result.succeeded


def test_windows_refuses_programs_outside_the_fixed_allow_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _pretend_windows(monkeypatch, tmp_path)

    def must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("an unlisted program must never be launched")

    monkeypatch.setattr(platform.subprocess, "run", must_not_run)

    for name in ("cmd", "python", r"..\evil.exe", r"C:\Temp\powershell.exe"):
        assert platform.run_command((name, "/c", "whoami")).failure is CommandFailure.NOT_FOUND
