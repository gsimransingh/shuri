from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from shuri import cli
from shuri.models import CheckResult, CheckStatus, Report

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(output: str) -> str:
    """Remove terminal colour codes that CI forces on, which can split a message."""
    return _ANSI.sub("", output)


def test_doctor_rejects_non_json_export() -> None:
    result = CliRunner().invoke(cli.app, ["doctor", "--format", "html"])

    assert result.exit_code != 0
    assert "Format must be json" in result.output


def test_doctor_rejects_output_without_json() -> None:
    result = CliRunner().invoke(cli.app, ["doctor", "--output", "report.json"])

    assert result.exit_code != 0
    assert "require --format json" in _plain(result.output)


def test_doctor_exports_json_without_saving_a_local_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report = Report.create((), "test-host")
    monkeypatch.setattr(cli, "_build_report", lambda: report)
    output = tmp_path / "report.json"

    result = CliRunner().invoke(
        cli.app, ["doctor", "--format", "json", "--output", str(output), "--raw"]
    )

    assert result.exit_code == 0
    assert output.is_file()
    assert '"hostname": "test-host"' in output.read_text(encoding="utf-8")
    assert "Raw export" in _plain(result.output)


def test_doctor_export_is_redacted_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "_build_report", lambda: Report.create((), "private-host"))
    output = tmp_path / "report.json"

    result = CliRunner().invoke(cli.app, ["doctor", "--format", "json", "--output", str(output)])

    assert result.exit_code == 0
    text = output.read_text(encoding="utf-8")
    assert "private-host" not in text
    assert '"redacted": true' in text
    assert "Raw export" not in _plain(result.output)


def test_doctor_will_not_overwrite_an_existing_export_without_force(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "_build_report", lambda: Report.create((), "host"))
    output = tmp_path / "report.json"
    output.write_text("precious", encoding="utf-8")
    arguments = ["doctor", "--format", "json", "--output", str(output)]

    refused = CliRunner().invoke(cli.app, arguments)
    forced = CliRunner().invoke(cli.app, [*arguments, "--force"])

    assert refused.exit_code != 0
    assert "--force" in _plain(refused.output)
    assert forced.exit_code == 0
    assert "precious" not in output.read_text(encoding="utf-8")


def test_doctor_rejects_conflicting_raw_and_redact_flags() -> None:
    result = CliRunner().invoke(cli.app, ["doctor", "-f", "json", "--raw", "--redact"])

    assert result.exit_code != 0


def test_diagnostic_show_renders_detailed_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    result = CheckResult(
        "network",
        "Network",
        CheckStatus.PASS,
        "Healthy.",
        metrics={"adapters": [{"name": "Wi-Fi", "is_up": True, "addresses": []}]},
    )
    monkeypatch.setattr(cli.DiagnosticRunner, "run", lambda _self, _names: (result,))

    command = CliRunner().invoke(cli.app, ["network", "show"])

    assert command.exit_code == 0
    assert "Network Adapters" in command.output


def test_removed_report_management_commands_are_not_exposed() -> None:
    result = CliRunner().invoke(cli.app, ["history"])

    assert result.exit_code != 0
    assert "No such command" in result.output
