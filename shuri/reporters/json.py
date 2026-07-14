"""Machine-readable JSON reporting."""

from __future__ import annotations

import json

from shuri.models import Report


def render_json(report: Report) -> str:
    """Serialise a report using stable, readable JSON."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
