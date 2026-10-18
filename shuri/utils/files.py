"""Safe report file writing."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from shuri.core.exceptions import ExportError


def write_report_file(path: Path, text: str, *, overwrite: bool = False) -> Path:
    """Write ``text`` to ``path`` without clobbering files or following symbolic links.

    Without ``overwrite`` the file is created exclusively, so an existing file or link is never
    touched. With ``overwrite`` the content is written to a private temporary file in the same
    directory and swapped in atomically; a link at ``path`` is replaced, never followed.
    """
    target = Path(path)
    if target.is_dir():
        raise ExportError(f"{target} is a directory; choose a file name.")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not overwrite:
            return _create_exclusively(target, text)
        return _replace_atomically(target, text)
    except FileExistsError:
        raise ExportError(f"{target} already exists; use --force to replace it.") from None
    except OSError as error:
        raise ExportError(f"Could not write {target}: {error.strerror or 'file error'}.") from None


def _create_exclusively(target: Path, text: str) -> Path:
    handle = target.open("x", encoding="utf-8")  # Raises, without touching it, if it exists.
    try:
        with handle:
            handle.write(text)
    except BaseException:
        with contextlib.suppress(OSError):
            target.unlink()
        raise
    return target


def _replace_atomically(target: Path, text: str) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent, prefix=".shuri-", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise
    return target
