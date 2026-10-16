from __future__ import annotations

import pytest

from shuri.checks.services import _parse_service_state


@pytest.mark.parametrize(
    ("state_line", "expected"),
    (
        ("        STATE              : 4  RUNNING", "running"),
        ("        STATE              : 1  STOPPED", "stopped"),
        ("        STATE              : 2  START_PENDING", "starting"),
        ("        STATE              : 5  CONTINUE_PENDING", "starting"),
        ("        STATE              : 3  STOP_PENDING", "stopped"),
        ("        STATE              : 7  PAUSED", "stopped"),
    ),
)
def test_service_states_are_parsed_from_the_state_line(state_line: str, expected: str) -> None:
    output = (
        "SERVICE_NAME: wuauserv\n"
        "        TYPE               : 20  WIN32_SHARE_PROCESS\n"
        f"{state_line}\n"
    )

    assert _parse_service_state(output) == expected


def test_unparseable_service_output_is_unavailable_not_stopped() -> None:
    assert _parse_service_state("") == "unavailable"
    assert _parse_service_state("something unexpected RUNNING") == "unavailable"
