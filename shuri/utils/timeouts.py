"""Bound calls that have no timeout of their own."""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable


def call_with_timeout[T](function: Callable[[], T], timeout: float, default: T) -> T:
    """Return ``function()``, or ``default`` if it raises or takes longer than ``timeout`` seconds.

    The call runs on a daemon thread, so a call that never returns is abandoned rather than
    blocking the caller or delaying program exit.
    """
    outcome: list[T] = []

    def target() -> None:
        with contextlib.suppress(Exception):
            outcome.append(function())

    thread = threading.Thread(target=target, name="shuri-bounded-call", daemon=True)
    thread.start()
    thread.join(timeout)
    return outcome[0] if outcome else default
