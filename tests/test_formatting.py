from __future__ import annotations

import pytest

from shuri.utils.formatting import format_bytes, format_duration


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1.0 KiB"),
        (5 * 1024**3, "5.0 GiB"),
    ],
)
def test_format_bytes(value: int, expected: str) -> None:
    assert format_bytes(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (45, "45s"),
        (3_661, "1h 1m"),
        (90_061, "1d 1h 1m"),
    ],
)
def test_format_duration(value: int, expected: str) -> None:
    assert format_duration(value) == expected


def test_formatters_reject_negative_values() -> None:
    with pytest.raises(ValueError):
        format_bytes(-1)
    with pytest.raises(ValueError):
        format_duration(-1)
