"""Tests for platform-neutral standalone executable naming."""

from scripts.build_standalone import executable_name


def test_windows_standalone_uses_exe_suffix() -> None:
    assert executable_name("Windows") == "shuri.exe"


def test_unix_standalone_has_no_suffix() -> None:
    assert executable_name("Linux") == "shuri"
    assert executable_name("Darwin") == "shuri"
