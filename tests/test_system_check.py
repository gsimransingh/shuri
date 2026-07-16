from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from shuri.checks import system


def test_collect_system_info_builds_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        system.platform,
        "uname",
        lambda: SimpleNamespace(
            node="workstation-01",
            system="TestOS",
            release="1.0",
            version="build-42",
            machine="x86_64",
            processor="Test CPU",
        ),
    )
    monkeypatch.setattr(system.platform, "python_version", lambda: "3.12.10")
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
    monkeypatch.setattr(system.psutil, "boot_time", lambda: 1_700_000_000.0)
    monkeypatch.setattr(system.psutil, "cpu_count", lambda logical: 8 if logical else 4)

    now = datetime.fromtimestamp(1_700_003_661.0, tz=timezone.utc)
    snapshot = system.collect_system_info(disk_path="/", now=now)

    assert snapshot.hostname == "workstation-01"
    assert snapshot.os_name == "TestOS"
    assert snapshot.physical_cores == 4
    assert snapshot.logical_cores == 8
    assert snapshot.memory_total_bytes == 16 * 1024**3
    assert snapshot.disk_free_bytes == 125 * 1024**3
    assert snapshot.uptime_seconds == 3_661


def test_collect_system_info_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        system.collect_system_info(now=datetime(2026, 1, 1))


def test_collect_system_info_wraps_operating_system_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> None:
        raise OSError("system unavailable")

    monkeypatch.setattr(system.psutil, "virtual_memory", fail)

    with pytest.raises(system.SystemInfoCollectionError, match="system unavailable"):
        system.collect_system_info()
