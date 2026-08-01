"""GitHub-friendly Markdown reporting."""

from __future__ import annotations

from html import escape

from shuri.models import Report
from shuri.utils.helpers import format_bytes


def _display_metric(value: object, key: str) -> str:
    if key.endswith("_bytes") and isinstance(value, (int, float)):
        return format_bytes(value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return "Unavailable"
    return str(value)


def _markdown_text(value: object) -> str:
    """Escape collected text so it cannot inject Markdown or raw HTML."""
    text = str(value).replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    text = escape(text, quote=False).replace("\\", "\\\\")
    for marker in ("`", "*", "_", "[", "]"):
        text = text.replace(marker, f"\\{marker}")
    return text


def _table_cell(value: object) -> str:
    return _markdown_text(value).replace("|", "\\|")


def render_markdown(report: Report) -> str:
    """Render a shareable Markdown health assessment."""
    lines = [
        "# Shuri Workstation Health Report",
        "",
        f"- **Host:** {_markdown_text(report.hostname)}",
        f"- **Generated:** {report.generated_at.isoformat()}",
        f"- **Scan duration:** {report.duration_ms / 1000:.1f}s",
        f"- **Redacted:** {'Yes' if report.redacted else 'No'}",
    ]
    if report.assessment:
        lines.extend(
            (
                f"- **Health:** {report.assessment.score}/100 — "
                f"{_markdown_text(report.assessment.label)}",
                f"- **Score calculation:** 100 - {report.assessment.total_deductions} "
                f"deduction point(s) = {report.assessment.score}",
                f"- **Coverage:** {report.assessment.completed_checks}/{len(report.results)} "
                f"checks completed ({report.assessment.coverage_percent:.1f}%)",
                "",
            )
        )
    else:
        lines.append("")
    lines.extend(
        (
            "## Diagnostics",
            "",
            "| Check | Status | Summary | Duration |",
            "| --- | --- | --- | ---: |",
        )
    )
    lines.extend(
        f"| {_table_cell(result.title)} | {result.status.value.upper()} | "
        f"{_table_cell(result.summary)} | "
        f"{result.duration_ms:.0f} ms |"
        for result in report.results
    )
    for result in report.results:
        lines.extend(("", f"## {_markdown_text(result.title)}", "", _markdown_text(result.summary)))
        scalar_metrics = {
            key: value
            for key, value in result.metrics.items()
            if not isinstance(value, (dict, list))
        }
        if scalar_metrics:
            lines.extend(("", "| Metric | Value |", "| --- | --- |"))
            lines.extend(
                f"| {_table_cell(key.replace('_', ' ').title())} | "
                f"{_table_cell(_display_metric(value, key))} |"
                for key, value in scalar_metrics.items()
            )
        if result.findings:
            lines.extend(("", "### Findings", ""))
            lines.extend(f"- {_markdown_text(finding)}" for finding in result.findings)
    if report.assessment and report.assessment.deductions:
        lines.extend(("", "## Score deductions", ""))
        lines.extend(
            f"- **-{item.points}** {_markdown_text(item.reason)} " f"({_markdown_text(item.check)})"
            for item in report.assessment.deductions
        )
    return "\n".join(lines) + "\n"
