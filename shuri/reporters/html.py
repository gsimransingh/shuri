"""Self-contained HTML reporting using a small Jinja template."""

from __future__ import annotations

from jinja2 import BaseLoader, Environment, select_autoescape

from shuri.models import Report
from shuri.utils.helpers import format_bytes

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shuri Health Report - {{ report.hostname }}</title>
  <style>
    body { font-family: Inter, Segoe UI, Arial, sans-serif; max-width: 1100px;
      margin: 36px auto; padding: 0 20px; color: #172033; background: #f7f9fc; }
    h1, h2, h3 { color: #102a43; }
    .card { background: #fff; border: 1px solid #d9e2ec; border-radius: 12px;
      padding: 20px; margin: 18px 0; box-shadow: 0 2px 8px #102a4308; }
    .score { font-size: 2rem; font-weight: 700; }
    .pass { color: #147d4c; } .warning { color: #a15c00; }
    .fail { color: #ba2525; } .unknown { color: #627d98; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    th, td { padding: 10px; text-align: left; border-bottom: 1px solid #d9e2ec;
      vertical-align: top; }
    th { color: #486581; background: #f0f4f8; }
    .tag { font-weight: 700; text-transform: uppercase; }
    .muted { color: #627d98; }
    .finding { margin: 8px 0; padding: 10px 12px; background: #fffbea;
      border-left: 4px solid #f0b429; }
    code { white-space: pre-wrap; word-break: break-word; font-size: .85rem; }
  </style>
</head>
<body>
  <header>
    <h1>Shuri Workstation Health Report</h1>
    <p class="muted">Host: <strong>{{ report.hostname }}</strong></p>
    <p class="muted">Generated: {{ report.generated_at.isoformat() }}
      · Shuri {{ report.shuri_version }}</p>
  </header>
  {% if report.assessment %}
  <section class="card">
    <div class="score">
      {{ report.assessment.score }}/100 - {{ report.assessment.label }}
    </div>
    {% if report.assessment.deductions %}
    <h3>Score deductions</h3>
    <ul>
      {% for item in report.assessment.deductions %}
      <li><strong>-{{ item.points }}</strong> {{ item.reason }}
        <span class="muted">({{ item.check }})</span></li>
      {% endfor %}
    </ul>
    {% endif %}
  </section>
  {% endif %}
  <section class="card">
    <h2>Diagnostics</h2>
    <table>
      <thead><tr><th>Check</th><th>Status</th><th>Summary</th></tr></thead>
      <tbody>
        {% for result in report.results %}
        <tr><td>{{ result.title }}</td>
          <td class="tag {{ result.status.value }}">{{ result.status.value }}</td>
          <td>{{ result.summary }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </section>
  {% for result in report.results %}
  <section class="card">
    <h2>{{ result.title }}</h2>
    <p class="{{ result.status.value }} tag">{{ result.status.value }}</p>
    <p>{{ result.summary }}</p>
    {% if result.findings %}
    <h3>Findings</h3>
    {% for finding in result.findings %}<p class="finding">{{ finding }}</p>{% endfor %}
    {% endif %}
    {% if result.metrics %}
    <h3>Collected data</h3>
    <table><tbody>
      {% for key, value in result.metrics.items() %}
      <tr><th>{{ key.replace('_', ' ').title() }}</th>
        <td>{% if value is mapping or value is sequence and value is not string %}
          <code>{{ value | tojson(indent=2) }}</code>{% else %}{{ value }}{% endif %}</td></tr>
      {% endfor %}
    </tbody></table>
    {% endif %}
  </section>
  {% endfor %}
</body>
</html>"""


def render_html(report: Report) -> str:
    """Render a standalone, shareable HTML report."""
    environment = Environment(loader=BaseLoader(), autoescape=select_autoescape(default=True))
    environment.filters["format_bytes"] = format_bytes
    return environment.from_string(_TEMPLATE).render(report=report)
