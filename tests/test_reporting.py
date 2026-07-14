from __future__ import annotations

from shuri.models import CheckResult, CheckStatus, Report
from shuri.reporters import render_html, render_json, render_markdown


def _report() -> Report:
    return Report.create(
        hostname="workstation-01",
        results=(
            CheckResult(
                name="cpu",
                title="CPU",
                status=CheckStatus.PASS,
                summary="CPU utilisation is normal.",
                metrics={"utilisation_percent": 12.5},
            ),
        ),
    )


def test_json_report_is_machine_readable() -> None:
    rendered = render_json(_report())

    assert '"hostname": "workstation-01"' in rendered
    assert '"status": "pass"' in rendered


def test_human_reporters_include_the_check_summary() -> None:
    report = _report()

    assert "CPU utilisation is normal." in render_markdown(report)
    assert "CPU utilisation is normal." in render_html(report)
