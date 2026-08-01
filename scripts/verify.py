"""Run Shuri's complete local and release verification workflow."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(label: str, command: tuple[str, ...], *, cwd: Path = ROOT) -> None:
    print(f"\n==> {label}", flush=True)
    subprocess.run(command, cwd=cwd, check=True, shell=False)


def _environment_executable(environment: Path, name: str) -> Path:
    directory = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return environment / directory / f"{name}{suffix}"


def main() -> int:
    python = sys.executable
    checks = (
        ("Tests", (python, "-m", "pytest")),
        ("Lint", (python, "-m", "ruff", "check", ".")),
        ("Formatting", (python, "-m", "black", "--check", ".")),
        ("Types", (python, "-m", "mypy", "shuri")),
    )
    try:
        for label, command in checks:
            _run(label, command)

        with tempfile.TemporaryDirectory(prefix="shuri-verify-") as temporary:
            temporary_path = Path(temporary)
            wheelhouse = temporary_path / "wheelhouse"
            wheelhouse.mkdir()
            _run(
                "Build wheel",
                (
                    python,
                    "-m",
                    "pip",
                    "wheel",
                    "--disable-pip-version-check",
                    "--no-deps",
                    "--wheel-dir",
                    str(wheelhouse),
                    str(ROOT),
                ),
            )
            wheels = tuple(wheelhouse.glob("shuri_cli-*.whl"))
            if len(wheels) != 1:
                raise RuntimeError(f"Expected one Shuri wheel, found {len(wheels)}.")

            smoke_environment = temporary_path / "smoke-environment"
            _run("Create clean smoke environment", (python, "-m", "venv", str(smoke_environment)))
            smoke_python = _environment_executable(smoke_environment, "python")
            smoke_shuri = _environment_executable(smoke_environment, "shuri")
            _run(
                "Install built wheel",
                (
                    str(smoke_python),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    str(wheels[0]),
                ),
                cwd=temporary_path,
            )
            _run("Smoke test version", (str(smoke_shuri), "version"), cwd=temporary_path)
            _run(
                "Smoke test non-privileged diagnostic",
                (str(smoke_shuri), "cpu"),
                cwd=temporary_path,
            )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\nVerification failed: {error}", file=sys.stderr)
        return 1

    print("\nAll verification steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
