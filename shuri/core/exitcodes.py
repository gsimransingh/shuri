"""Process exit codes that let scripts act on a scan without parsing its output."""

from __future__ import annotations

from collections.abc import Iterable
from enum import IntEnum

from shuri.models import CheckResult, CheckStatus


class ExitCode(IntEnum):
    """What a scan tells the calling shell."""

    OK = 0
    WARNING = 1
    FAILED = 2
    INCOMPLETE = 3


def exit_code_for(results: Iterable[CheckResult]) -> ExitCode:
    """Return the most severe outcome: failed, then incomplete, then warning, then ok.

    A failure outranks missing evidence because it is a confirmed problem. Missing evidence
    outranks a warning because the machine cannot be called ready without it.
    """
    statuses = {result.status for result in results}
    if CheckStatus.FAIL in statuses:
        return ExitCode.FAILED
    if CheckStatus.UNKNOWN in statuses:
        return ExitCode.INCOMPLETE
    if CheckStatus.WARNING in statuses:
        return ExitCode.WARNING
    return ExitCode.OK
