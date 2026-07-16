from __future__ import annotations

from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from shuri import cli
from shuri.checks import system


def test_system_check_includes_workstation_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system.socket, "gethostname", lambda: "workstation-01")
    monkeypatch.setattr(system.platform, "system", lambda: "TestOS")
    monkeypatch.setattr(system.platform, "release", lambda: "1.0")
    monkeypatch.setattr(system.platform, "version", lambda: "build-42")
    monkeypatch.setattr(system.platform, "platform", lambda: "TestOS-1.0")
    monkeypatch.setattr(system.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(system.platform, "processor", lambda: "Test CPU")
    monkeypatch.setattr(system.platform, "python_version", lambda: "3.12.10")
    monkeypatch.setattr(system.psutil, "boot_time", lambda: 1_700_000_000.0)
    monkeypatch.setattr(system.psutil, "cpu_count", lambda logical: 8 if logical else 4)
    monkeypatch.setattr(
        system.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=16 * 1024**3, available=8 * 1024**3),
    )
    monkeypatch.setattr(
        system.psutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=500 * 1024**3, free=125 * 1024**3),
    )

    result = system.check_system()

    assert result.title == "System Information"
    assert result.metrics["hostname"] == "workstation-01"
    assert result.metrics["processor"] == "Test CPU"
    assert result.metrics["physical_cores"] == 4
    assert result.metrics["logical_cores"] == 8
    assert result.metrics["memory_total_bytes"] == 16 * 1024**3
    assert result.metrics["system_disk_free_bytes"] == 125 * 1024**3
    assert result.metrics["python_version"] == "3.12.10"


def test_system_info_command_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    selected: list[str] = []
    monkeypatch.setattr(cli, "_single_check", selected.append)

    result = CliRunner().invoke(cli.app, ["system-info"])

    assert result.exit_code == 0
    assert selected == ["system"]
