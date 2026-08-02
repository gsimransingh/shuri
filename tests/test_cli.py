from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from shuri import cli
from shuri.core.exceptions import ReportStorageError
from shuri.core.scoring import assess_health
from shuri.models import CheckResult, CheckStatus, Report


def test_doctor_rejects_output_without_a_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "_build_report",
        lambda *args, **kwargs: pytest.fail("scan should not start for invalid options"),
    )

    with pytest.raises(typer.BadParameter, match="--output requires"):
        cli.doctor(
            report_format=None,
            html=False,
            json_format=False,
            markdown=False,
            output=Path("report.json"),
            redact=False,
        )


def test_report_rejects_unknown_format(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "load_latest_report", lambda: Report.create((), "test-host"))

    result = CliRunner().invoke(
        cli.app, ["report", "--format", "xml", "--output", str(tmp_path / "report.xml")]
    )

    assert result.exit_code != 0
    assert "Unsupported format" in result.output


def test_report_turns_storage_errors_into_actionable_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_load() -> None:
        raise ReportStorageError("Saved report is incompatible; run 'shuri doctor' again.")

    monkeypatch.setattr(cli, "load_latest_report", fail_load)

    result = CliRunner().invoke(cli.app, ["report"])

    assert result.exit_code == 1
    assert "run 'shuri doctor' again" in result.output


def test_history_lists_retained_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    report = Report.create((), "test-host", assess_health(()))
    monkeypatch.setattr(cli, "load_report_history", lambda **_kwargs: (report,))

    result = CliRunner().invoke(cli.app, ["history"])

    assert result.exit_code == 0
    assert "Report History" in result.output
    assert "test-host" in result.output


def test_history_clear_requires_explicit_confirmation() -> None:
    result = CliRunner().invoke(cli.app, ["history", "--clear"])

    assert result.exit_code != 0
    assert "requires --clear --yes" in result.output


def test_compare_uses_selected_assessed_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    newer_result = CheckResult("cpu", "CPU", CheckStatus.PASS, "Healthy")
    older_result = CheckResult("cpu", "CPU", CheckStatus.WARNING, "Elevated")
    newer = Report.create((newer_result,), "host", assess_health((newer_result,)))
    older = Report.create((older_result,), "host", assess_health((older_result,)))
    monkeypatch.setattr(cli, "load_report_history", lambda **_kwargs: (newer, older))

    result = CliRunner().invoke(cli.app, ["compare"])

    assert result.exit_code == 0
    assert "Health Comparison" in result.output
    assert "WARNING" in result.output
    assert "PASS" in result.output


def test_compare_explains_when_history_is_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "load_report_history", lambda **_kwargs: ())

    result = CliRunner().invoke(cli.app, ["compare"])

    assert result.exit_code == 1
    assert "Only 0 assessed historical report" in result.output
