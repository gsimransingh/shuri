"""Windows pending-reboot detection."""

from __future__ import annotations

import json

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import is_windows, run_powershell


def _registry_key_exists(path: str) -> bool:
    import winreg

    try:
        with winreg.OpenKey(  # type: ignore[attr-defined, unused-ignore]
            winreg.HKEY_LOCAL_MACHINE, path  # type: ignore[attr-defined, unused-ignore]
        ):
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _registry_value_exists(path: str, name: str) -> bool:
    import winreg

    try:
        with winreg.OpenKey(  # type: ignore[attr-defined, unused-ignore]
            winreg.HKEY_LOCAL_MACHINE, path  # type: ignore[attr-defined, unused-ignore]
        ) as key:
            winreg.QueryValueEx(key, name)  # type: ignore[attr-defined, unused-ignore]
    except (FileNotFoundError, OSError):
        return False
    return True


def pending_reboot() -> bool:
    """Return whether common Windows update/restart registry markers are present."""
    if not is_windows():
        return False
    return any(
        _registry_key_exists(path)
        for path in (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
        )
    ) or _registry_value_exists(
        r"SYSTEM\CurrentControlSet\Control\Session Manager", "PendingFileRenameOperations"
    )


def available_update_count() -> int | None:
    """Return available Windows Update count, or ``None`` if the agent cannot be queried."""
    if not is_windows():
        return None
    output = run_powershell(
        "$session = New-Object -ComObject Microsoft.Update.Session; "
        "$searcher = $session.CreateUpdateSearcher(); "
        "$result = $searcher.Search('IsInstalled=0 and IsHidden=0'); "
        "[PSCustomObject]@{ PendingUpdates = $result.Updates.Count } | ConvertTo-Json -Compress",
        timeout=20,
    )
    if output is None:
        return None
    try:
        data = json.loads(output)
        count = data.get("PendingUpdates") if isinstance(data, dict) else None
        return int(count) if isinstance(count, int | float | str) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def check_updates() -> CheckResult:
    """Assess pending reboot state and available Windows Updates without changing state."""
    if not is_windows():
        return CheckResult(
            name="updates",
            title="Windows Update",
            status=CheckStatus.UNKNOWN,
            summary="Windows Update diagnostics are not available on this platform.",
        )
    reboot_pending = pending_reboot()
    update_count = available_update_count()
    deductions: list[ScoreDeduction] = []
    findings: list[str] = []
    status = CheckStatus.PASS
    if reboot_pending:
        status = CheckStatus.WARNING
        findings.append("Restart the workstation to complete a pending update or servicing action.")
        deductions.append(ScoreDeduction("A Windows restart is pending", 5, "updates"))
    if update_count is None:
        status = CheckStatus.UNKNOWN if status is CheckStatus.PASS else status
        findings.append("Windows Update availability could not be queried.")
    elif update_count > 0:
        status = CheckStatus.WARNING if status is CheckStatus.PASS else status
        findings.append(f"{update_count} Windows update(s) are available.")
        deductions.append(ScoreDeduction("Windows updates are available", 3, "updates"))
    if status is CheckStatus.PASS:
        summary = "No pending reboot or available Windows updates were found."
    elif reboot_pending and update_count is not None:
        summary = f"Restart pending; {update_count} update(s) available."
    elif reboot_pending:
        summary = "A Windows restart is pending."
    elif update_count is None:
        summary = "No pending reboot found, but update availability is unknown."
    else:
        summary = f"{update_count} Windows update(s) are available."
    return CheckResult(
        name="updates",
        title="Windows Update",
        status=status,
        summary=summary,
        metrics={
            "pending_reboot": reboot_pending,
            "available_updates": update_count,
            "update_query_available": update_count is not None,
        },
        findings=tuple(findings),
        deductions=tuple(deductions),
    )
