from __future__ import annotations

import json

import pytest

from shuri.checks import eventlogs, network
from shuri.models import CheckStatus
from shuri.models.network import AdapterSnapshot
from shuri.utils.platform import CommandFailure, CommandResult, OperatingSystem


@pytest.mark.parametrize(
    ("has_adapter", "dns_succeeded", "tcp_succeeded", "expected"),
    (
        (True, True, True, CheckStatus.PASS),
        (True, False, True, CheckStatus.WARNING),
        (False, False, False, CheckStatus.FAIL),
    ),
)
def test_network_status_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    has_adapter: bool,
    dns_succeeded: bool,
    tcp_succeeded: bool,
    expected: CheckStatus,
) -> None:
    adapters = (
        (AdapterSnapshot("Ethernet", True, ("192.0.2.10",), "00:11:22:33:44:55"),)
        if has_adapter
        else ()
    )
    monkeypatch.setattr(network, "_adapter_snapshots", lambda: adapters)
    monkeypatch.setattr(network, "_windows_network_configuration", lambda: (None, (), None))
    monkeypatch.setattr(network, "_probe_configuration", lambda: ("dns.test", "tcp.test", 443))
    monkeypatch.setattr(network, "_can_resolve", lambda _host: dns_succeeded)
    monkeypatch.setattr(network, "_can_connect", lambda _host, _port: tcp_succeeded)

    assert network.check_network().status is expected


def test_partial_windows_network_configuration_is_a_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        network,
        "_adapter_snapshots",
        lambda: (AdapterSnapshot("Ethernet", True, ("192.0.2.10",), None),),
    )
    monkeypatch.setattr(
        network,
        "_windows_network_configuration",
        lambda: (None, (), "Windows network configuration timed out."),
    )
    monkeypatch.setattr(network, "_probe_configuration", lambda: ("dns.test", "tcp.test", 443))
    monkeypatch.setattr(network, "_can_resolve", lambda _host: True)
    monkeypatch.setattr(network, "_can_connect", lambda _host, _port: True)

    result = network.check_network()

    assert result.status is CheckStatus.WARNING
    assert result.metrics["configuration_complete"] is False
    assert "configuration partial" in result.summary
    assert result.deductions == ()


@pytest.mark.parametrize(
    ("levels", "expected"),
    (
        ((), CheckStatus.PASS),
        ((2, 2, 2, 2, 2), CheckStatus.WARNING),
        ((1,), CheckStatus.FAIL),
    ),
)
def test_event_log_status_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    levels: tuple[int, ...],
    expected: CheckStatus,
) -> None:
    payload = json.dumps([{"Level": level} for level in levels])
    monkeypatch.setattr(eventlogs, "operating_system", lambda: OperatingSystem.WINDOWS)
    monkeypatch.setattr(
        eventlogs, "run_powershell", lambda *_args, **_kwargs: CommandResult(payload)
    )

    assert eventlogs.check_event_logs().status is expected


def test_event_log_command_failure_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eventlogs, "operating_system", lambda: OperatingSystem.WINDOWS)
    monkeypatch.setattr(
        eventlogs,
        "run_powershell",
        lambda *_args, **_kwargs: CommandResult(failure=CommandFailure.ACCESS_DENIED),
    )

    result = eventlogs.check_event_logs()

    assert result.status is CheckStatus.UNKNOWN
    assert "sufficient access" in result.summary
