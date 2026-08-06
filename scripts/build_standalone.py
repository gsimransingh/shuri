"""Build and smoke-test a native single-file Shuri executable."""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def executable_name(system: str | None = None) -> str:
    """Return the native executable filename for the build platform."""
    return "shuri.exe" if (system or platform.system()) == "Windows" else "shuri"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "dist" / "standalone",
        help="Directory that receives the native Shuri executable.",
    )
    arguments = parser.parse_args()
    output = arguments.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    executable = output / executable_name()
    with tempfile.TemporaryDirectory(prefix="shuri-standalone-") as temporary:
        temporary_path = Path(temporary)
        subprocess.run(
            (
                sys.executable,
                "-m",
                "PyInstaller",
                "--onefile",
                "--clean",
                "--noconfirm",
                "--name",
                "shuri",
                "--distpath",
                str(output),
                "--workpath",
                str(temporary_path / "build"),
                "--specpath",
                str(temporary_path / "spec"),
                str(ROOT / "shuri" / "__main__.py"),
            ),
            cwd=ROOT,
            check=True,
            shell=False,
        )
        subprocess.run((str(executable), "version"), cwd=temporary_path, check=True, shell=False)
        subprocess.run((str(executable), "cpu"), cwd=temporary_path, check=True, shell=False)
    print(f"Standalone executable verified: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
