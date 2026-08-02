"""Build and smoke-test a single-file Windows Shuri executable."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "dist" / "standalone",
        help="Directory that receives shuri.exe.",
    )
    arguments = parser.parse_args()
    if os.name != "nt":
        parser.error("The standalone executable must be built on Windows.")
    output = arguments.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    executable = output / "shuri.exe"
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
