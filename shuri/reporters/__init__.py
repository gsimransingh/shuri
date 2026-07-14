"""Pure renderers for Shuri report data."""

from __future__ import annotations

from shuri.reporters.html import render_html
from shuri.reporters.json import render_json
from shuri.reporters.markdown import render_markdown

__all__ = ["render_html", "render_json", "render_markdown"]
