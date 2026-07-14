"""Windows pending-reboot detection."""

from __future__ import annotations

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.utils.platform import is_windows


def _registry_key_exists(path: str) -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path):
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


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
    )


def check_updates() -> CheckResult:
    """Check the actionable, low-cost update signal: a pending reboot."""
    if not is_windows():
        return CheckResult(
            name="updates",
            title="Windows Update",
            status=CheckStatus.UNKNOWN,
            summary="Windows Update diagnostics are not available on this platform.",
        )
    reboot_pending = pending_reboot()
    if reboot_pending:
        return CheckResult(
            name="updates",
            title="Windows Update",
            status=CheckStatus.WARNING,
            summary="A Windows restart is pending.",
            metrics={"pending_reboot": True},
            findings=("Restart the workstation to complete a pending update or servicing action.",),
            deductions=(ScoreDeduction("A Windows restart is pending", 5, "updates"),),
        )
    return CheckResult(
        name="updates",
        title="Windows Update",
        status=CheckStatus.PASS,
        summary="No common pending-reboot marker was found.",
        metrics={"pending_reboot": False},
    )
