"""Domain-specific exceptions."""

from __future__ import annotations


class ShuriError(Exception):
    """Base error for expected Shuri domain failures."""


class UnknownDiagnosticError(ShuriError):
    """Raised when a named diagnostic is not registered."""
