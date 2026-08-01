from __future__ import annotations

from shuri.core.scoring import assess_health
from shuri.models import CheckResult, CheckStatus, Report, ScoreDeduction
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


def test_reports_include_the_explicit_score_calculation() -> None:
    result = CheckResult(
        name="disk",
        title="Disk",
        status=CheckStatus.WARNING,
        summary="Disk is low.",
        deductions=(ScoreDeduction("System drive is below 15% free", 8, "disk"),),
    )
    report = Report.create(
        hostname="workstation-01",
        results=(result,),
        assessment=assess_health((result,)),
    )

    assert '"total_deductions": 8' in render_json(report)
    assert "100 - 8 deduction point(s) = 92" in render_markdown(report)
    assert "100 - 8 deduction point(s)" in render_html(report)


def test_reports_expose_incomplete_assessment_coverage() -> None:
    result = CheckResult("updates", "Updates", CheckStatus.UNKNOWN, "Unavailable")
    report = Report.create((result,), "workstation-01", assess_health((result,)))

    rendered_json = render_json(report)
    assert '"label": "Incomplete"' in rendered_json
    assert '"coverage_percent": 0.0' in rendered_json
    assert "0/1 checks completed" in render_markdown(report)
    assert "0/1" in render_html(report)


def test_reporters_escape_collected_text() -> None:
    result = CheckResult(
        name="unsafe",
        title="Unsafe | check",
        status=CheckStatus.WARNING,
        summary="<script>alert(1)</script> | next\nrow",
        metrics={"unsafe_value": "<img src=x> | value"},
        findings=("[click](javascript:alert(1))",),
    )
    report = Report.create((result,), "<host>")

    markdown = render_markdown(report)
    html = render_html(report)

    assert "<script>" not in markdown
    assert "Unsafe \\| check" in markdown
    assert "next row" in markdown
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
