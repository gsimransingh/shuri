from __future__ import annotations

import pytest

from shuri.checks import services
from shuri.checks.services import _parse_service_state, _parse_start_type, _problem, _ServiceStatus
from shuri.models import CheckStatus


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        ("running", "running"),
        ("RUNNING", "running"),
        ("stopped", "stopped"),
        ("start_pending", "starting"),
        ("continue_pending", "starting"),
        ("stop_pending", "stopped"),
        ("pause_pending", "stopped"),
        ("paused", "stopped"),
    ),
)
def test_service_states_are_translated_from_psutil(status: str, expected: str) -> None:
    assert _parse_service_state(status) == expected


def test_unrecognised_service_state_is_unavailable_not_stopped() -> None:
    assert _parse_service_state("") == "unavailable"
    assert _parse_service_state("something unexpected") == "unavailable"


@pytest.mark.parametrize(
    ("start_type", "delayed", "expected"),
    (
        ("manual", False, "manual"),
        ("automatic", False, "auto"),
        ("automatic", True, "delayed_auto"),
        ("manual", True, "manual"),
        ("disabled", False, "disabled"),
        ("boot", False, "boot"),
        ("system", False, "system"),
        ("something_new", False, "unknown"),
        ("", False, "unknown"),
    ),
)
def test_start_type_is_translated_from_psutil(
    start_type: str, delayed: bool, expected: str
) -> None:
    assert _parse_start_type(start_type, delayed=delayed) == expected


def _status(state: str, start_type: str) -> _ServiceStatus:
    return _ServiceStatus(state, start_type)


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


class _FakeService:
    def __init__(self, status: str, start_type: str) -> None:
        self._status = status
        self._start_type = start_type

    def status(self) -> str:
        return self._status

    def start_type(self) -> str:
        return self._start_type


def _fake_services(
    monkeypatch: pytest.MonkeyPatch,
    states: dict[str, str],
    start_types: dict[str, str],
    *,
    uptime: float = 9999,
    delayed: frozenset[str] = frozenset(),
) -> None:
    def get(name: str) -> _FakeService:
        return _FakeService(states[name], start_types[name])

    monkeypatch.setattr(services, "is_windows", lambda: True)
    monkeypatch.setattr(services.psutil, "win_service_get", get, raising=False)
    monkeypatch.setattr(services, "_is_delayed_autostart", lambda name: name in delayed)
    monkeypatch.setattr(services, "_seconds_since_boot", lambda: uptime)
    monkeypatch.setattr(services.time, "sleep", lambda _seconds: None)


_DEFAULT_STATES = {
    name: "running" for name in ("WinDefend", "eventlog", "BITS", "Dhcp", "Dnscache", "wuauserv")
}
_DEFAULT_STARTS = {
    "WinDefend": "automatic",
    "eventlog": "automatic",
    "BITS": "manual",
    "Dhcp": "automatic",
    "Dnscache": "automatic",
    "wuauserv": "manual",
}


def test_idle_on_demand_windows_update_is_not_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: a real PC had wuauserv Stopped with StartType Manual (normal)."""
    _fake_services(monkeypatch, {**_DEFAULT_STATES, "wuauserv": "stopped"}, _DEFAULT_STARTS)

    result = services.check_services()

    assert result.status is CheckStatus.PASS
    assert result.findings == ()
    assert result.deductions == ()
    assert result.metrics["services"]["wuauserv"]["start_type"] == "manual"


def test_disabled_windows_update_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_services(
        monkeypatch,
        {**_DEFAULT_STATES, "wuauserv": "stopped"},
        {**_DEFAULT_STARTS, "wuauserv": "disabled"},
    )

    result = services.check_services()

    assert result.status is CheckStatus.WARNING
    assert result.findings == ("Windows Update is disabled.",)
    assert result.deductions == ()


def test_stopped_critical_service_fails_with_a_deduction(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_services(monkeypatch, {**_DEFAULT_STATES, "Dnscache": "stopped"}, _DEFAULT_STARTS)

    result = services.check_services()

    assert result.status is CheckStatus.FAIL
    assert result.findings == ("DNS Client is not running.",)
    assert result.deductions[0].reason == "Critical service DNS Client is not running"


def test_service_stuck_starting_is_reported_not_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_services(monkeypatch, {**_DEFAULT_STATES, "Dhcp": "start_pending"}, _DEFAULT_STARTS)

    result = services.check_services()

    assert result.status is CheckStatus.WARNING
    assert result.findings == ("DHCP Client is still starting.",)
    assert result.deductions == ()


def test_service_that_finishes_starting_during_recheck_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_services(monkeypatch, {**_DEFAULT_STATES, "Dhcp": "start_pending"}, _DEFAULT_STARTS)
    queries = {"count": 0}

    def settling(name: str) -> _FakeService:
        if name == "Dhcp":
            queries["count"] += 1
            if queries["count"] >= 2:
                return _FakeService("running", "automatic")
            return _FakeService("start_pending", "automatic")
        return _FakeService(_DEFAULT_STATES[name], _DEFAULT_STARTS[name])

    monkeypatch.setattr(services.psutil, "win_service_get", settling, raising=False)

    assert services.check_services().status is CheckStatus.PASS


def test_delayed_start_service_is_given_a_grace_period_after_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_services(
        monkeypatch,
        {**_DEFAULT_STATES, "BITS": "stopped"},
        {**_DEFAULT_STARTS, "BITS": "automatic"},
        uptime=60,
        delayed=frozenset({"BITS"}),
    )

    result = services.check_services()

    assert result.metrics["services"]["BITS"]["start_type"] == "delayed_auto"
    assert result.status is CheckStatus.PASS


def test_unreadable_services_are_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(name: str) -> _FakeService:
        raise services.psutil.AccessDenied()

    monkeypatch.setattr(services, "is_windows", lambda: True)
    monkeypatch.setattr(services.psutil, "win_service_get", denied, raising=False)

    assert services.check_services().status is CheckStatus.UNKNOWN


def test_service_queries_are_unavailable_without_psutil_windows_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(services, "is_windows", lambda: True)
    monkeypatch.delattr(services.psutil, "win_service_get", raising=False)

    assert services.check_services().status is CheckStatus.UNKNOWN
