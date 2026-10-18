from __future__ import annotations

import pytest

from shuri.checks import services
from shuri.checks.services import _parse_service_state, _parse_start_type, _problem, _ServiceStatus
from shuri.models import CheckStatus
from shuri.utils.platform import CommandFailure, CommandResult


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


@pytest.mark.parametrize(
    ("start_line", "expected"),
    (
        ("        START_TYPE         : 3   DEMAND_START", "manual"),
        ("        START_TYPE         : 2   AUTO_START", "auto"),
        ("        START_TYPE         : 2   AUTO_START  (DELAYED)", "delayed_auto"),
        ("        START_TYPE         : 4   DISABLED", "disabled"),
        ("        START_TYPE         : 0   BOOT_START", "boot"),
        ("        START_TYPE         : 1   SYSTEM_START", "system"),
        ("        START_TYPE         : 9   SOMETHING_NEW", "unknown"),
    ),
)
def test_start_type_is_parsed_from_its_numeric_code(start_line: str, expected: str) -> None:
    assert _parse_start_type(f"[SC] QueryServiceConfig SUCCESS\n{start_line}\n") == expected


def test_missing_start_type_is_unknown() -> None:
    assert _parse_start_type("") == "unknown"


def _status(state: str, start_type: str) -> _ServiceStatus:
    return _ServiceStatus(state, start_type, CommandResult())


@pytest.mark.parametrize(
    ("name", "state", "start_type", "uptime", "expected"),
    (
        ("wuauserv", "stopped", "manual", 9999, None),
        ("BITS", "stopped", "manual", 9999, None),
        ("wuauserv", "stopped", "disabled", 9999, "is disabled"),
        ("wuauserv", "stopped", "auto", 9999, "is not running"),
        ("wuauserv", "stopped", "unknown", 9999, "is not running (start type unavailable)"),
        ("BITS", "stopped", "delayed_auto", 60, None),
        ("BITS", "stopped", "delayed_auto", 9999, "is not running"),
        ("BITS", "stopped", "delayed_auto", None, "is not running"),
        ("eventlog", "stopped", "auto", 9999, "is not running"),
        ("eventlog", "stopped", "manual", 9999, "is not running"),
        ("eventlog", "stopped", "disabled", 9999, "is disabled"),
        ("Dhcp", "starting", "auto", 9999, "is still starting"),
        ("wuauserv", "running", "manual", 9999, None),
        ("wuauserv", "unavailable", "unknown", 9999, None),
    ),
)
def test_service_problem_depends_on_how_the_service_should_run(
    name: str, state: str, start_type: str, uptime: float | None, expected: str | None
) -> None:
    assert _problem(name, _status(state, start_type), uptime) == expected


def _fake_sc(
    monkeypatch: pytest.MonkeyPatch,
    states: dict[str, str],
    start_types: dict[str, int],
    *,
    uptime: float = 9999,
) -> None:
    labels = {"RUNNING": "4  RUNNING", "STOPPED": "1  STOPPED", "START_PENDING": "2  START_PENDING"}
    kinds = {0: "0   BOOT_START", 2: "2   AUTO_START", 3: "3   DEMAND_START", 4: "4   DISABLED"}

    def run(command: tuple[str, ...], timeout: float = 5.0) -> CommandResult:
        verb, name = command[1], command[2]
        if verb == "query":
            return CommandResult(f"SERVICE_NAME: {name}\n        STATE : {labels[states[name]]}\n")
        return CommandResult(f"[SC] OK\n        START_TYPE : {kinds[start_types[name]]}\n")

    monkeypatch.setattr(services, "is_windows", lambda: True)
    monkeypatch.setattr(services, "run_command", run)
    monkeypatch.setattr(services, "_seconds_since_boot", lambda: uptime)
    monkeypatch.setattr(services.time, "sleep", lambda _seconds: None)


_DEFAULT_STATES = {
    name: "RUNNING" for name in ("WinDefend", "eventlog", "BITS", "Dhcp", "Dnscache", "wuauserv")
}
_DEFAULT_STARTS = {
    "WinDefend": 2,
    "eventlog": 2,
    "BITS": 3,
    "Dhcp": 2,
    "Dnscache": 2,
    "wuauserv": 3,
}


def test_idle_on_demand_windows_update_is_not_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: a real PC had wuauserv Stopped with StartType Manual (normal)."""
    _fake_sc(monkeypatch, {**_DEFAULT_STATES, "wuauserv": "STOPPED"}, _DEFAULT_STARTS)

    result = services.check_services()

    assert result.status is CheckStatus.PASS
    assert result.findings == ()
    assert result.deductions == ()
    assert result.metrics["services"]["wuauserv"]["start_type"] == "manual"


def test_disabled_windows_update_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_sc(
        monkeypatch,
        {**_DEFAULT_STATES, "wuauserv": "STOPPED"},
        {**_DEFAULT_STARTS, "wuauserv": 4},
    )

    result = services.check_services()

    assert result.status is CheckStatus.WARNING
    assert result.findings == ("Windows Update is disabled.",)
    assert result.deductions == ()


def test_stopped_critical_service_fails_with_a_deduction(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_sc(monkeypatch, {**_DEFAULT_STATES, "Dnscache": "STOPPED"}, _DEFAULT_STARTS)

    result = services.check_services()

    assert result.status is CheckStatus.FAIL
    assert result.findings == ("DNS Client is not running.",)
    assert result.deductions[0].reason == "Critical service DNS Client is not running"


def test_service_stuck_starting_is_reported_not_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_sc(monkeypatch, {**_DEFAULT_STATES, "Dhcp": "START_PENDING"}, _DEFAULT_STARTS)

    result = services.check_services()

    assert result.status is CheckStatus.WARNING
    assert result.findings == ("DHCP Client is still starting.",)
    assert result.deductions == ()


def test_service_that_finishes_starting_during_recheck_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_sc(monkeypatch, {**_DEFAULT_STATES, "Dhcp": "START_PENDING"}, _DEFAULT_STARTS)
    original = services.run_command
    queries = {"count": 0}

    def settling(command: tuple[str, ...], timeout: float = 5.0) -> CommandResult:
        if command[1:] == ("query", "Dhcp"):
            queries["count"] += 1
            if queries["count"] >= 2:
                return CommandResult("SERVICE_NAME: Dhcp\n        STATE : 4  RUNNING\n")
        return original(command, timeout)

    monkeypatch.setattr(services, "run_command", settling)

    assert services.check_services().status is CheckStatus.PASS


def test_unreadable_services_are_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "is_windows", lambda: True)
    monkeypatch.setattr(
        services,
        "run_command",
        lambda *_a, **_k: CommandResult(failure=CommandFailure.ACCESS_DENIED),
    )

    assert services.check_services().status is CheckStatus.UNKNOWN
