from __future__ import annotations

import pytest

from shuri.core.exitcodes import ExitCode, exit_code_for
from shuri.models import CheckResult, CheckStatus


def _results(*statuses: CheckStatus) -> tuple[CheckResult, ...]:
    return tuple(CheckResult(f"c{i}", "C", status, "s") for i, status in enumerate(statuses))


@pytest.mark.parametrize(
    ("statuses", "expected"),
    (
        ((), ExitCode.OK),
        ((CheckStatus.PASS, CheckStatus.PASS), ExitCode.OK),
        ((CheckStatus.PASS, CheckStatus.WARNING), ExitCode.WARNING),
        ((CheckStatus.WARNING, CheckStatus.UNKNOWN), ExitCode.INCOMPLETE),
        ((CheckStatus.PASS, CheckStatus.UNKNOWN), ExitCode.INCOMPLETE),
        ((CheckStatus.UNKNOWN, CheckStatus.FAIL), ExitCode.FAILED),
        ((CheckStatus.FAIL, CheckStatus.WARNING, CheckStatus.PASS), ExitCode.FAILED),
    ),
)
def test_exit_code_reflects_the_most_severe_outcome(
    statuses: tuple[CheckStatus, ...], expected: ExitCode
) -> None:
    assert exit_code_for(_results(*statuses)) is expected


def test_exit_code_values_are_stable() -> None:
    assert [code.value for code in ExitCode] == [0, 1, 2, 3]
