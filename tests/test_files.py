from __future__ import annotations

import os
from pathlib import Path

import pytest

from shuri.core.exceptions import ExportError
from shuri.utils.files import write_report_file


def test_new_file_is_created_and_parent_directories_are_made(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "report.json"

    assert write_report_file(target, "data") == target
    assert target.read_text(encoding="utf-8") == "data"


def test_existing_file_is_preserved_unless_overwrite_is_requested(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    target.write_text("original", encoding="utf-8")

    with pytest.raises(ExportError, match="--force"):
        write_report_file(target, "new")
    assert target.read_text(encoding="utf-8") == "original"

    write_report_file(target, "new", overwrite=True)
    assert target.read_text(encoding="utf-8") == "new"
    assert [item.name for item in tmp_path.iterdir()] == ["report.json"]


def test_directory_target_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ExportError, match="directory"):
        write_report_file(tmp_path, "data")


def test_symbolic_link_target_is_never_followed(tmp_path: Path) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me", encoding="utf-8")
    link = tmp_path / "report.json"
    try:
        os.symlink(victim, link)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are not available to this user.")

    with pytest.raises(ExportError):
        write_report_file(link, "overwritten")
    assert victim.read_text(encoding="utf-8") == "keep me"

    write_report_file(link, "replaced", overwrite=True)
    assert victim.read_text(encoding="utf-8") == "keep me"
    assert not link.is_symlink()
