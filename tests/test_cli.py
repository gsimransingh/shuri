from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from shuri import cli
from shuri.core.exceptions import ReportStorageError
from shuri.models import Report


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
