"""Deterministic coverage for Linux and macOS native collectors."""

from __future__ import annotations

import json
import plistlib

import pytest

from shuri.checks import antivirus, eventlogs, native_unix, physical_drives, services, updates
from shuri.models import CheckStatus
from shuri.utils.platform import CommandFailure, CommandResult, OperatingSystem


@pytest.mark.parametrize(
    ("module", "function", "active_os", "target"),
    (
        (services, "check_services", OperatingSystem.LINUX, "check_linux_services"),
        (updates, "check_updates", OperatingSystem.MACOS, "check_macos_updates"),
        (antivirus, "check_antivirus", OperatingSystem.LINUX, "check_linux_security"),
        (eventlogs, "check_event_logs", OperatingSystem.MACOS, "check_macos_logs"),
        (physical_drives, "check_physical_drives", OperatingSystem.LINUX, "check_linux_drives"),
    ),
)
def test_public_checks_dispatch_to_native_collector(
    monkeypatch: pytest.MonkeyPatch,
    module: object,
    function: str,
    active_os: OperatingSystem,
    target: str,
) -> None:
    expected = native_unix.unsupported_native_check("test", "Test", active_os)
    monkeypatch.setattr(module, "operating_system", lambda: active_os)
    monkeypatch.setattr(native_unix, target, lambda: expected)

    assert getattr(module, function)() is expected


def test_linux_services_use_systemd_state(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = {
        ("systemctl", "is-system-running"): CommandResult("running\n"),
        (
            "systemctl",
            "show",
            "systemd-journald.service",
            "--property=LoadState,ActiveState",
        ): CommandResult("LoadState=loaded\nActiveState=active\n"),
    }
    monkeypatch.setattr(
        native_unix,
        "run_command",
        lambda command, **_kwargs: outputs.get(
            tuple(command), CommandResult("LoadState=not-found\n")
        ),
    )

    result = native_unix.check_linux_services()

    assert result.status is CheckStatus.PASS
    assert result.metrics["services"]["systemd-journald.service"]["state"] == "running"


def test_linux_apt_updates_are_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native_unix.Path, "exists", lambda _path: False)
    monkeypatch.setattr(
        native_unix,
        "run_command",
        lambda *_args, **_kwargs: CommandResult(
            "Listing...\npackage-a/stable 2 amd64 [upgradable from: 1]\n"
        ),
    )

    result = native_unix.check_linux_updates()

    assert result.status is CheckStatus.WARNING
    assert result.metrics["available_updates"] == 1
    assert result.metrics["source"] == "apt"


def test_macos_updates_are_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        native_unix,
        "run_command",
        lambda *_args, **_kwargs: CommandResult(
            "Software Update Tool\n   * Label: macOS 15.1\n   * Label: Safari 19\n"
        ),
    )

    result = native_unix.check_macos_updates()

    assert result.status is CheckStatus.WARNING
    assert result.metrics["available_updates"] == 2


def test_linux_security_reports_native_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    def command_result(command: tuple[str, ...], **_kwargs: object) -> CommandResult:
        if command[0] == "ufw":
            return CommandResult("Status: active\n")
        if command[0] == "aa-status":
            return CommandResult("apparmor module is loaded.\n")
        return CommandResult(failure=CommandFailure.NOT_FOUND)

    monkeypatch.setattr(native_unix, "run_command", command_result)

    result = native_unix.check_linux_security()

    assert result.status is CheckStatus.PASS
    assert result.metrics["security_controls"]["firewall"][0] == "enabled"


def test_linux_journal_metadata_is_bounded_and_scored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines = [
        json.dumps(
            {
                "PRIORITY": "3",
                "__REALTIME_TIMESTAMP": "1",
                "SYSLOG_IDENTIFIER": "kernel",
                "_SYSTEMD_UNIT": "kernel.service",
            }
        )
        for _ in range(5)
    ]
    monkeypatch.setattr(
        native_unix, "run_command", lambda *_args, **_kwargs: CommandResult("\n".join(lines))
    )

    result = native_unix.check_linux_logs()

    assert result.status is CheckStatus.WARNING
    assert result.metrics["errors"] == 5
    assert "MESSAGE" not in result.metrics["recent_events"][0]


def test_macos_log_accepts_newline_delimited_json(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = "\n".join(
        json.dumps(
            {
                "timestamp": str(index),
                "messageType": "Error",
                "processID": index,
                "subsystem": "com.example.test",
            }
        )
        for index in range(5)
    )
    monkeypatch.setattr(
        native_unix, "run_command", lambda *_args, **_kwargs: CommandResult(payload)
    )

    result = native_unix.check_macos_logs()

    assert result.status is CheckStatus.WARNING
    assert result.metrics["errors"] == 5


def test_linux_drive_smart_failure_is_native_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory = json.dumps(
        {
            "blockdevices": [
                {
                    "name": "sda",
                    "model": "Test SSD",
                    "type": "disk",
                    "tran": "sata",
                    "size": 1000,
                    "rota": False,
                }
            ]
        }
    )

    def command_result(command: tuple[str, ...], **_kwargs: object) -> CommandResult:
        return (
            CommandResult(inventory)
            if command[0] == "lsblk"
            else CommandResult('{"smart_status":{"passed":false}}')
        )

    monkeypatch.setattr(native_unix, "run_command", command_result)

    assert native_unix.check_linux_drives().status is CheckStatus.FAIL


def test_macos_diskutil_smart_status_is_native_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing = plistlib.dumps({"WholeDisks": ["disk0"]}).decode()
    info = plistlib.dumps(
        {
            "SMARTStatus": "Verified",
            "MediaName": "Apple SSD",
            "SolidState": True,
            "BusProtocol": "PCI",
            "TotalSize": 1000,
        }
    ).decode()
    monkeypatch.setattr(
        native_unix,
        "run_command",
        lambda command, **_kwargs: CommandResult(listing if command[1] == "list" else info),
    )

    assert native_unix.check_macos_drives().status is CheckStatus.PASS
