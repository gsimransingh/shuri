"""Read-only Linux and macOS diagnostics behind a shared result contract."""

from __future__ import annotations

import json
import plistlib
import re
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from shuri.core.policy import DEFAULT_POLICY
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.models.physical_drive import PhysicalDriveSnapshot
from shuri.utils.platform import (
    CommandFailure,
    CommandResult,
    OperatingSystem,
    command_failure_message,
    run_command,
)

_MAX_EVENTS = 50


def _unknown(name: str, title: str, subject: str, result: CommandResult) -> CheckResult:
    return CheckResult(name, title, CheckStatus.UNKNOWN, command_failure_message(subject, result))


def _state_result(
    *,
    name: str,
    title: str,
    states: dict[str, dict[str, str]],
    critical: Iterable[str],
) -> CheckResult:
    critical_names = set(critical)
    stopped = [key for key, value in states.items() if value["state"] != "running"]
    stopped_critical = [key for key in stopped if key in critical_names]
    status = (
        CheckStatus.FAIL
        if stopped_critical
        else CheckStatus.WARNING if stopped else CheckStatus.PASS
    )
    deductions = tuple(
        ScoreDeduction(
            f"Critical service {states[key]['display_name']} is not running",
            DEFAULT_POLICY.stopped_service_points,
            "services",
        )
        for key in stopped_critical
    )
    return CheckResult(
        name,
        title,
        status,
        f"Checked {len(states)} native system services.",
        metrics={"services": states},
        findings=tuple(f"{states[key]['display_name']} is not running." for key in stopped),
        deductions=deductions,
    )


def check_linux_services() -> CheckResult:
    """Inspect a small, portable set of systemd service roles."""
    overall = run_command(("systemctl", "is-system-running"))
    if overall.failure in {CommandFailure.NOT_FOUND, CommandFailure.ACCESS_DENIED}:
        return _unknown("services", "System Services", "systemd service status", overall)
    candidates = {
        "systemd-journald.service": ("System journal", True),
        "systemd-udevd.service": ("Device manager", True),
        "dbus.service": ("System message bus", True),
        "NetworkManager.service": ("Network manager", False),
        "systemd-resolved.service": ("DNS resolver", False),
        "unattended-upgrades.service": ("Automatic updates", False),
    }
    states: dict[str, dict[str, str]] = {}
    critical: list[str] = []
    for unit, (label, required) in candidates.items():
        loaded = run_command(("systemctl", "show", unit, "--property=LoadState,ActiveState"))
        if loaded.failure is not None or "LoadState=not-found" in loaded.output:
            continue
        active = re.search(r"^ActiveState=(.+)$", loaded.output, re.MULTILINE)
        state = "running" if active and active.group(1) == "active" else "stopped"
        states[unit] = {"display_name": label, "state": state}
        if required:
            critical.append(unit)
    if not states:
        return _unknown("services", "System Services", "systemd service inventory", overall)
    return _state_result(name="services", title="System Services", states=states, critical=critical)


def check_macos_services() -> CheckResult:
    """Inspect essential launchd jobs visible to the current user."""
    candidates = {
        "system/com.apple.logd": ("Unified logging", True),
        "system/com.apple.metadata.mds": ("Metadata service", False),
    }
    states: dict[str, dict[str, str]] = {}
    critical: list[str] = []
    last_result = CommandResult(failure=CommandFailure.NOT_FOUND)
    for key, (label, required) in candidates.items():
        last_result = run_command(("launchctl", "print", key))
        if not last_result.succeeded:
            continue
        state = (
            "running" if re.search(r"\bstate\s*=\s*running\b", last_result.output) else "stopped"
        )
        states[key] = {"display_name": label, "state": state}
        if required:
            critical.append(key)
    if not states:
        return _unknown("services", "System Services", "launchd service status", last_result)
    return _state_result(name="services", title="System Services", states=states, critical=critical)


def _update_result(count: int, reboot_pending: bool, source: str) -> CheckResult:
    status = CheckStatus.WARNING if count or reboot_pending else CheckStatus.PASS
    findings: list[str] = []
    deductions: list[ScoreDeduction] = []
    if reboot_pending:
        findings.append("Restart the workstation to complete pending system maintenance.")
        deductions.append(
            ScoreDeduction(
                "A system restart is pending", DEFAULT_POLICY.pending_restart_points, "updates"
            )
        )
    if count:
        findings.append(f"{count} system update(s) are available.")
        deductions.append(
            ScoreDeduction(
                "System updates are available", DEFAULT_POLICY.available_updates_points, "updates"
            )
        )
    return CheckResult(
        "updates",
        "System Updates",
        status,
        (
            "No pending restart or available system updates were found."
            if status is CheckStatus.PASS
            else (
                f"{count} update(s) available; restart "
                f"{'pending' if reboot_pending else 'not pending'}."
            )
        ),
        metrics={
            "pending_reboot": reboot_pending,
            "available_updates": count,
            "update_query_available": True,
            "source": source,
        },
        findings=tuple(findings),
        deductions=tuple(deductions),
    )


def check_linux_updates() -> CheckResult:
    """Query available updates through an installed Linux package manager."""
    reboot_pending = Path("/var/run/reboot-required").exists()
    apt = run_command(("apt", "list", "--upgradable"), timeout=20)
    if apt.succeeded:
        count = sum(
            1 for line in apt.output.splitlines() if "/" in line and not line.startswith("Listing")
        )
        return _update_result(count, reboot_pending, "apt")
    dnf = run_command(("dnf", "--quiet", "check-update"), timeout=20)
    if dnf.succeeded or dnf.exit_code == 100:
        count = sum(1 for line in dnf.output.splitlines() if len(line.split()) >= 3)
        return _update_result(count, reboot_pending, "dnf")
    pacman = run_command(("checkupdates",), timeout=20)
    if pacman.succeeded or pacman.exit_code == 2:
        count = len([line for line in pacman.output.splitlines() if line.strip()])
        return _update_result(count, reboot_pending, "pacman")
    return _unknown("updates", "System Updates", "Linux update availability", apt)


def check_macos_updates() -> CheckResult:
    """Query macOS Software Update without installing anything."""
    result = run_command(("softwareupdate", "--list"), timeout=30)
    if not result.succeeded:
        return _unknown("updates", "System Updates", "macOS update availability", result)
    count = len(re.findall(r"^\s*\* Label:", result.output, re.MULTILINE))
    restart_pending = bool(re.search(r"restart|required", result.output, re.IGNORECASE))
    return _update_result(count, restart_pending, "softwareupdate")


def _control(command: tuple[str, ...], enabled_markers: tuple[str, ...]) -> tuple[str, str]:
    result = run_command(command)
    if not result.succeeded:
        return "unknown", command_failure_message(command[0], result)
    normalized = result.output.casefold()
    enabled = any(marker in normalized for marker in enabled_markers)
    return ("enabled" if enabled else "disabled"), result.output.strip()[:200]


def _security_result(platform_name: str, controls: dict[str, tuple[str, str]]) -> CheckResult:
    known = {key: value for key, value in controls.items() if value[0] != "unknown"}
    if not known:
        return CheckResult(
            "antivirus",
            "Security Posture",
            CheckStatus.UNKNOWN,
            f"{platform_name} security controls could not be verified.",
            metrics={"security_controls": controls},
        )
    disabled = [key for key, value in known.items() if value[0] == "disabled"]
    status = CheckStatus.WARNING if disabled else CheckStatus.PASS
    return CheckResult(
        "antivirus",
        "Security Posture",
        status,
        f"Verified {len(known)} of {len(controls)} native security controls.",
        metrics={"security_controls": controls},
        findings=tuple(f"{key.replace('_', ' ').title()} is disabled." for key in disabled),
        deductions=(
            (
                ScoreDeduction(
                    "Native security controls are disabled",
                    DEFAULT_POLICY.realtime_antivirus_disabled_points,
                    "antivirus",
                ),
            )
            if disabled
            else ()
        ),
    )


def check_linux_security() -> CheckResult:
    """Assess available Linux firewall and mandatory-access controls."""
    firewall = _control(("ufw", "status"), ("status: active",))
    if firewall[0] == "unknown":
        firewall = _control(("firewall-cmd", "--state"), ("running",))
    apparmor = _control(("aa-status",), ("module is loaded", "profiles are loaded"))
    if apparmor[0] == "unknown":
        apparmor = _control(("getenforce",), ("enforcing", "permissive"))
    return _security_result("Linux", {"firewall": firewall, "mandatory_access_control": apparmor})


def check_macos_security() -> CheckResult:
    """Assess built-in macOS platform security controls."""
    return _security_result(
        "macOS",
        {
            "gatekeeper": _control(("spctl", "--status"), ("assessments enabled",)),
            "system_integrity_protection": _control(("csrutil", "status"), ("status: enabled",)),
            "filevault": _control(("fdesetup", "status"), ("filevault is on",)),
            "firewall": _control(
                ("/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"),
                ("enabled",),
            ),
        },
    )


def _event_result(entries: list[dict[str, object]], source: str) -> CheckResult:
    entries = entries[: _MAX_EVENTS + 1]
    truncated = len(entries) > _MAX_EVENTS
    entries = entries[:_MAX_EVENTS]
    critical = sum(1 for entry in entries if entry.get("level") == "critical")
    errors = sum(1 for entry in entries if entry.get("level") == "error")
    warnings = sum(1 for entry in entries if entry.get("level") == "warning")
    status = (
        CheckStatus.FAIL
        if critical
        else (
            CheckStatus.WARNING
            if errors >= DEFAULT_POLICY.repeated_error_event_count
            else CheckStatus.PASS
        )
    )
    deductions: list[ScoreDeduction] = []
    if critical:
        deductions.append(
            ScoreDeduction(
                "Recent critical system events were found",
                DEFAULT_POLICY.critical_event_points,
                "eventlogs",
            )
        )
    if errors >= DEFAULT_POLICY.repeated_error_event_count:
        deductions.append(
            ScoreDeduction(
                "Five or more recent system errors were found",
                DEFAULT_POLICY.repeated_error_event_points,
                "eventlogs",
            )
        )
    return CheckResult(
        "eventlogs",
        "System Logs",
        status,
        f"Last 24 hours: {critical} critical, {errors} errors, {warnings} warnings.",
        metrics={
            "critical": critical,
            "errors": errors,
            "warnings": warnings,
            "window_hours": 24,
            "truncated": truncated,
            "maximum_events": _MAX_EVENTS,
            "recent_events": entries,
            "source": source,
        },
        deductions=tuple(deductions),
    )


def check_linux_logs() -> CheckResult:
    """Read a bounded set of recent systemd journal warnings and errors."""
    result = run_command(
        (
            "journalctl",
            "--since",
            "24 hours ago",
            "--priority",
            "warning",
            "--output",
            "json",
            "--no-pager",
            "--lines",
            str(_MAX_EVENTS + 1),
        ),
        timeout=10,
    )
    if not result.succeeded:
        return _unknown("eventlogs", "System Logs", "system journal", result)
    entries: list[dict[str, object]] = []
    levels = {"0": "critical", "1": "critical", "2": "critical", "3": "error", "4": "warning"}
    for line in result.output.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        entries.append(
            {
                "time_created": item.get("__REALTIME_TIMESTAMP", "Unavailable"),
                "level": levels.get(str(item.get("PRIORITY")), "warning"),
                "event_id": item.get("SYSLOG_IDENTIFIER", "Unavailable"),
                "provider": item.get("_SYSTEMD_UNIT", item.get("_COMM", "Unavailable")),
            }
        )
    return _event_result(entries, "journalctl")


def check_macos_logs() -> CheckResult:
    """Read bounded macOS unified-log error metadata without message bodies."""
    result = run_command(
        (
            "log",
            "show",
            "--last",
            "1d",
            "--style",
            "json",
            "--predicate",
            "messageType == error OR messageType == fault",
        ),
        timeout=10,
    )
    if not result.succeeded:
        return _unknown("eventlogs", "System Logs", "macOS unified log", result)
    try:
        parsed = json.loads(result.output or "[]")
        items = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        items = []
        for line in result.output.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                items.append(item)
    if result.output.strip() and not items:
        return CheckResult(
            "eventlogs",
            "System Logs",
            CheckStatus.UNKNOWN,
            "macOS unified log returned invalid structured data.",
        )
    entries = [
        {
            "time_created": item.get("timestamp", "Unavailable"),
            "level": "critical" if item.get("messageType") == "Fault" else "error",
            "event_id": item.get("processID", "Unavailable"),
            "provider": item.get("subsystem", item.get("processImagePath", "Unavailable")),
        }
        for item in items
        if isinstance(item, dict)
    ]
    return _event_result(entries, "unified_log")


def _linux_drives(payload: str) -> tuple[PhysicalDriveSnapshot, ...]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return ()
    devices = data.get("blockdevices", []) if isinstance(data, dict) else []
    return tuple(
        PhysicalDriveSnapshot(
            device_id=f"/dev/{item.get('name', '')}",
            model=str(item.get("model") or "Unknown").strip(),
            media_type="SSD" if item.get("rota") in (False, 0) else "HDD",
            bus_type=str(item.get("tran") or "Unknown"),
            health_status="Unknown",
            operational_status=("Unknown",),
            size_bytes=int(item.get("size") or 0),
        )
        for item in devices
        if isinstance(item, dict)
        and item.get("type") == "disk"
        and isinstance(item.get("size"), int)
    )


def check_linux_drives() -> CheckResult:
    """Collect Linux physical-drive inventory and optional SMART health."""
    result = run_command(
        ("lsblk", "--bytes", "--json", "--output", "NAME,MODEL,TYPE,TRAN,SIZE,ROTA")
    )
    if not result.succeeded:
        return _unknown(
            "physical_drives", "Physical Drives", "Linux block-device inventory", result
        )
    drives = list(_linux_drives(result.output))
    if not drives:
        return CheckResult(
            "physical_drives",
            "Physical Drives",
            CheckStatus.UNKNOWN,
            "Linux returned no physical-drive inventory.",
        )
    enriched: list[PhysicalDriveSnapshot] = []
    for drive in drives:
        smart = run_command(("smartctl", "--health", "--json", drive.device_id))
        health = "Unknown"
        operational = ("Unknown",)
        if smart.output:
            try:
                smart_data = json.loads(smart.output)
                passed = smart_data.get("smart_status", {}).get("passed")
                if isinstance(passed, bool):
                    health = "Healthy" if passed else "Unhealthy"
                    operational = ("OK" if passed else "Predictive Failure",)
            except (AttributeError, json.JSONDecodeError):
                pass
        enriched.append(
            PhysicalDriveSnapshot(
                **{**asdict(drive), "health_status": health, "operational_status": operational}
            )
        )
    from shuri.checks.physical_drives import build_physical_drive_result

    return build_physical_drive_result(tuple(enriched), platform_name="Linux")


def check_macos_drives() -> CheckResult:
    """Collect macOS whole-disk inventory and built-in SMART status."""
    listing = run_command(("diskutil", "list", "-plist"))
    if not listing.succeeded:
        return _unknown("physical_drives", "Physical Drives", "macOS disk inventory", listing)
    try:
        data = plistlib.loads(listing.output.encode())
    except (plistlib.InvalidFileException, ValueError):
        return CheckResult(
            "physical_drives",
            "Physical Drives",
            CheckStatus.UNKNOWN,
            "macOS returned invalid disk inventory data.",
        )
    drives: list[PhysicalDriveSnapshot] = []
    for device in data.get("WholeDisks", []):
        info = run_command(("diskutil", "info", "-plist", str(device)))
        if not info.succeeded:
            continue
        try:
            item = plistlib.loads(info.output.encode())
        except (plistlib.InvalidFileException, ValueError):
            continue
        smart = str(item.get("SMARTStatus", "Unknown"))
        health = (
            "Healthy" if smart == "Verified" else "Unhealthy" if smart == "Failing" else "Unknown"
        )
        drives.append(
            PhysicalDriveSnapshot(
                device_id=f"/dev/{device}",
                model=str(item.get("MediaName", "Unknown")),
                media_type="SSD" if item.get("SolidState") else "HDD",
                bus_type=str(item.get("BusProtocol", "Unknown")),
                health_status=health,
                operational_status=("OK" if health == "Healthy" else smart,),
                size_bytes=int(item.get("TotalSize", 0)),
            )
        )
    if not drives:
        return CheckResult(
            "physical_drives",
            "Physical Drives",
            CheckStatus.UNKNOWN,
            "macOS returned no usable physical-drive evidence.",
        )
    from shuri.checks.physical_drives import build_physical_drive_result

    return build_physical_drive_result(tuple(drives), platform_name="macOS")


def unsupported_native_check(name: str, title: str, os_name: OperatingSystem) -> CheckResult:
    """Return an honest result for operating systems without a native adapter."""
    return CheckResult(
        name,
        title,
        CheckStatus.UNKNOWN,
        f"Native diagnostics are not implemented for {os_name.value}.",
    )
