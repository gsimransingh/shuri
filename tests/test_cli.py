from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from shuri import cli
from shuri.core import assess_health
from shuri.core.registry import DiagnosticRegistry
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
    monkeypatch.setattr(cli, "_build_report", lambda **_kwargs: report)
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
    monkeypatch.setattr(cli, "_build_report", lambda **_kwargs: Report.create((), "private-host"))
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
    monkeypatch.setattr(cli, "_build_report", lambda **_kwargs: Report.create((), "host"))
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


def _report_with(*statuses: CheckStatus) -> Report:
    results = tuple(CheckResult(f"c{i}", "C", status, "s") for i, status in enumerate(statuses))
    return Report.create(results, "host", assess_health(results))


@pytest.mark.parametrize(
    ("statuses", "expected"),
    (
        ((CheckStatus.PASS,), 0),
        ((CheckStatus.WARNING,), 1),
        ((CheckStatus.FAIL,), 2),
        ((CheckStatus.UNKNOWN,), 3),
    ),
)
def test_doctor_exit_code_reports_the_outcome(
    monkeypatch: pytest.MonkeyPatch, statuses: tuple[CheckStatus, ...], expected: int
) -> None:
    monkeypatch.setattr(cli, "_build_report", lambda **_kwargs: _report_with(*statuses))

    assert CliRunner().invoke(cli.app, ["doctor"]).exit_code == expected


def test_single_check_exit_code_reports_the_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    failing = CheckResult("disk", "Disk", CheckStatus.FAIL, "Low space")
    monkeypatch.setattr(cli.DiagnosticRunner, "run", lambda _self, _names: (failing,))

    assert CliRunner().invoke(cli.app, ["disk"]).exit_code == 2


def test_incomplete_scan_headline_does_not_present_a_perfect_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli, "_build_report", lambda **_kwargs: _report_with(CheckStatus.PASS, CheckStatus.UNKNOWN)
    )

    output = _plain(CliRunner().invoke(cli.app, ["doctor"]).output)

    assert "Incomplete" in output
    assert "partial score" in output
    assert "100/100 — Incomplete" not in output


def test_debug_flag_prints_tracebacks_for_failed_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = DiagnosticRegistry()

    def explode() -> CheckResult:
        raise RuntimeError("visible only with --debug")

    registry.register("cpu", explode)
    monkeypatch.setattr(cli, "default_registry", lambda **_kwargs: registry)

    quiet = CliRunner().invoke(cli.app, ["cpu"])
    loud = CliRunner().invoke(cli.app, ["--debug", "cpu"])

    assert "visible only with --debug" not in quiet.output
    assert "visible only with --debug" in loud.output
    assert "RuntimeError" in quiet.output
