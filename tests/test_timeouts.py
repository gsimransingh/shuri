from __future__ import annotations

from threading import Event
from time import monotonic

from shuri.utils.timeouts import call_with_timeout


def test_returns_the_result_when_the_call_finishes_in_time() -> None:
    assert call_with_timeout(lambda: 42, 1.0, -1) == 42


def test_returns_the_default_when_the_call_raises() -> None:
    def fail() -> int:
        raise ValueError("bad")

    assert call_with_timeout(fail, 1.0, -1) == -1


def test_returns_the_default_without_waiting_for_a_hung_call() -> None:
    release = Event()
    started = monotonic()

    result = call_with_timeout(lambda: release.wait(10), 0.2, "timed out")
    release.set()

    assert result == "timed out"
    assert monotonic() - started < 2
