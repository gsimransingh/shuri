from __future__ import annotations

from datetime import datetime, timezone

from typer.testing import CliRunner

from shuri import cli
from shuri.checks.system import SystemInfoCollectionError
from shuri.models.system import SystemInfo

runner = CliRunner()


def _snapshot() -> SystemInfo:
    return SystemInfo(
        hostname="workstation-01",
        os_name="TestOS",
        os_release="1.0",
        os_version="build-42",
        architecture="x86_64",
        processor="Test CPU",
        python_version="3.12.10",
        physical_cores=4,
        logical_cores=8,
        memory_total_bytes=16 * 1024**3,
        memory_available_bytes=8 * 1024**3,
        disk_total_bytes=500 * 1024**3,
        disk_free_bytes=125 * 1024**3,
        boot_time_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        uptime_seconds=3_661,
    )


def test_system_info_command(monkeypatch) -> None:
    monkeypatch.setattr(cli, "collect_system_info", _snapshot)

    result = runner.invoke(cli.app, ["system-info"])

    assert result.exit_code == 0
    assert "System Information" in result.output
    assert "workstation-01" in result.output


def test_system_info_command_reports_collection_error(monkeypatch) -> None:
    def fail() -> SystemInfo:
        raise SystemInfoCollectionError("system unavailable")

    monkeypatch.setattr(cli, "collect_system_info", fail)

    result = runner.invoke(cli.app, ["system-info"])

    assert result.exit_code == 1
    assert "Unable to collect system information: system unavailable" in result.output
