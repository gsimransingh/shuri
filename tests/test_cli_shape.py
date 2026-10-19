"""The simplified command line: `shuri`, `shuri check <name>`, and the opt-in --probe."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from shuri import cli
from shuri.checks import network
from shuri.core import default_registry
from shuri.models import CheckResult, CheckStatus, Report
from shuri.models.network import AdapterSnapshot

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(output: str) -> str:
    return _ANSI.sub("", output)


def _passing_report() -> Report:
    return Report.create((CheckResult("cpu", "CPU", CheckStatus.PASS, "ok"),), "private-host")


@pytest.fixture
def scans(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace the real scan with a stub and record how it was called."""
    calls: list[dict[str, Any]] = []

    def build(**kwargs: Any) -> Report:
        calls.append(kwargs)
        return _passing_report()

    monkeypatch.setattr(cli, "_build_report", build)
    return calls


def test_running_shuri_with_no_arguments_runs_the_full_scan(scans: list[dict[str, Any]]) -> None:
    result = CliRunner().invoke(cli.app, [])

    assert result.exit_code == 0
    assert scans == [{"probe": False}]
    assert "shuri --details" in _plain(result.output)


def test_details_flag_is_passed_to_the_report(
    monkeypatch: pytest.MonkeyPatch, scans: list[dict[str, Any]]
) -> None:
    shown: list[bool] = []
    monkeypatch.setattr(cli, "show_report", lambda _report, *, details: shown.append(details))

    CliRunner().invoke(cli.app, ["--details"])
    CliRunner().invoke(cli.app, [])

    assert shown == [True, False]


def test_probe_flag_enables_the_network_probes(scans: list[dict[str, Any]]) -> None:
    CliRunner().invoke(cli.app, ["--probe"])

    assert scans == [{"probe": True}]


def test_json_option_saves_a_redacted_report(scans: list[dict[str, Any]], tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    result = CliRunner().invoke(cli.app, ["--json", str(target)])

    text = target.read_text(encoding="utf-8")
    assert result.exit_code == 0
    assert "private-host" not in text
    assert '"redacted": true' in text
    assert "shuri --details" not in _plain(result.output)


def test_raw_json_keeps_identifiers_and_warns(scans: list[dict[str, Any]], tmp_path: Path) -> None:
    target = tmp_path / "report.json"

    result = CliRunner().invoke(cli.app, ["--json", str(target), "--raw"])

    assert "private-host" in target.read_text(encoding="utf-8")
    assert "Raw export" in _plain(result.output)


def test_json_will_not_replace_a_file_without_force(
    scans: list[dict[str, Any]], tmp_path: Path
) -> None:
    target = tmp_path / "report.json"
    target.write_text("keep", encoding="utf-8")

    refused = CliRunner().invoke(cli.app, ["--json", str(target)])
    forced = CliRunner().invoke(cli.app, ["--json", str(target), "--force"])

    assert refused.exit_code != 0
    assert target.read_text(encoding="utf-8") != "keep"
    assert forced.exit_code == 0


@pytest.mark.parametrize("flag", ("--raw", "--force"))
def test_raw_and_force_require_json(scans: list[dict[str, Any]], flag: str) -> None:
    result = CliRunner().invoke(cli.app, [flag])

    assert result.exit_code != 0
    assert "--json" in _plain(result.output)
    assert scans == []


def test_scan_options_placed_before_a_command_are_rejected_with_guidance(
    scans: list[dict[str, Any]],
) -> None:
    result = CliRunner().invoke(cli.app, ["--details", "check", "cpu"])

    assert result.exit_code != 0
    collapsed = re.sub(r"\s+", " ", _plain(result.output) + str(result.exception))
    assert "shuri check cpu --details" in collapsed


def test_check_command_runs_one_check_and_resolves_the_drives_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, bool, bool]] = []
    monkeypatch.setattr(
        cli,
        "_run_check",
        lambda name, *, details, probe: seen.append((name, details, probe)),
    )

    CliRunner().invoke(cli.app, ["check", "cpu", "--details"])
    CliRunner().invoke(cli.app, ["check", "DRIVES"])
    CliRunner().invoke(cli.app, ["check", "network", "--probe"])

    assert seen == [
        ("cpu", True, False),
        ("physical_drives", False, False),
        ("network", False, True),
    ]


def test_check_command_rejects_unknown_names_and_lists_the_valid_ones() -> None:
    result = CliRunner().invoke(cli.app, ["check", "bogus"])

    assert result.exit_code != 0
    collapsed = re.sub(r"\s+", " ", _plain(result.output) + str(result.exception))
    assert "physical_drives" in collapsed


def test_check_names_match_the_registry() -> None:
    assert default_registry().names() == cli.CHECK_NAMES


def test_old_doctor_command_still_works_but_is_hidden_and_deprecated(
    scans: list[dict[str, Any]], tmp_path: Path
) -> None:
    target = tmp_path / "report.json"

    result = CliRunner().invoke(cli.app, ["doctor", "show", "-f", "json", "-o", str(target)])
    help_text = _plain(CliRunner().invoke(cli.app, ["--help"]).output)

    assert result.exit_code == 0
    assert "Deprecated" in _plain(result.output)
    assert target.is_file()
    assert "doctor" not in help_text
    assert "check" in help_text


def test_old_per_check_commands_still_work_but_do_not_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, bool, bool]] = []
    monkeypatch.setattr(
        cli,
        "_run_check",
        lambda name, *, details, probe: seen.append((name, details, probe)),
    )

    result = CliRunner().invoke(cli.app, ["network", "show"])

    assert "Deprecated" in _plain(result.output)
    assert seen == [("network", True, False)]


def test_network_check_makes_no_network_calls_unless_probing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object) -> bool:
        raise AssertionError("the network was touched without --probe")

    monkeypatch.setattr(network, "_can_resolve", forbidden)
    monkeypatch.setattr(network, "_can_connect", forbidden)
    monkeypatch.setattr(
        network,
        "_adapter_snapshots",
        lambda: (AdapterSnapshot("Ethernet", True, ("10.0.0.5",), "aa:bb:cc:dd:ee:ff"),),
    )
    monkeypatch.setattr(network, "_windows_network_configuration", lambda: (None, (), None))

    result = default_registry().get("network")()

    assert result.status is CheckStatus.PASS
    assert result.metrics["probes_run"] is False
    assert "dns_probe" not in result.metrics
    assert "probes not run" in result.summary
    assert result.deductions == ()


def test_registry_probe_flag_turns_the_probes_on(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(network, "_can_resolve", lambda _host: called.append("dns") or True)
    monkeypatch.setattr(network, "_can_connect", lambda _h, _p: called.append("tcp") or True)
    monkeypatch.setattr(
        network,
        "_adapter_snapshots",
        lambda: (AdapterSnapshot("Ethernet", True, ("10.0.0.5",), None),),
    )
    monkeypatch.setattr(network, "_windows_network_configuration", lambda: (None, (), None))

    result = default_registry(probe=True).get("network")()

    assert called == ["dns", "tcp"]
    assert result.metrics["probes_run"] is True
    assert result.metrics["dns_probe"]["succeeded"] is True
