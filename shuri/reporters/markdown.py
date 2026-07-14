"""GitHub-friendly Markdown reporting."""

from __future__ import annotations

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


def render_markdown(report: Report) -> str:
    """Render a shareable Markdown health assessment."""
    lines = [
        "# Shuri Workstation Health Report",
        "",
        f"- **Host:** {report.hostname}",
        f"- **Generated:** {report.generated_at.isoformat()}",
    ]
    if report.assessment:
        lines.extend(
            (f"- **Health:** {report.assessment.score}/100 — {report.assessment.label}", "")
        )
    else:
        lines.append("")
    lines.extend(("## Diagnostics", "", "| Check | Status | Summary |", "| --- | --- | --- |"))
    lines.extend(
        f"| {result.title} | {result.status.value.upper()} | {result.summary} |"
        for result in report.results
    )
    for result in report.results:
        lines.extend(("", f"## {result.title}", "", result.summary))
        scalar_metrics = {
            key: value
            for key, value in result.metrics.items()
            if not isinstance(value, (dict, list))
        }
        if scalar_metrics:
            lines.extend(("", "| Metric | Value |", "| --- | --- |"))
            lines.extend(
                f"| {key.replace('_', ' ').title()} | {_display_metric(value, key)} |"
                for key, value in scalar_metrics.items()
            )
        if result.findings:
            lines.extend(("", "### Findings", ""))
            lines.extend(f"- {finding}" for finding in result.findings)
    if report.assessment and report.assessment.deductions:
        lines.extend(("", "## Score deductions", ""))
        lines.extend(
            f"- **-{item.points}** {item.reason} ({item.check})"
            for item in report.assessment.deductions
        )
    return "\n".join(lines) + "\n"
