# Reproducible development and standalone builds

Shuri's tested Python 3.12 dependency graph is pinned in
`requirements/constraints-py312.txt`. Project metadata declares direct compatibility ranges; the
constraints file supplies the exact graph used for development, CI, verification, and executable
builds.

## Verify a checkout

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements\constraints-py312.txt -e ".[dev]"
.\.venv\Scripts\python.exe scripts\verify.py
```

The verifier checks formatting, linting, typing, tests, package build, clean wheel installation,
and the installed `shuri` command.

## Build a native executable

```powershell
.\.venv\Scripts\python.exe -m pip install -c requirements\constraints-py312.txt -e ".[standalone]"
.\.venv\Scripts\python.exe scripts\build_standalone.py
.\dist\standalone\shuri.exe doctor
```

On Linux and macOS, create the environment with `python3 -m venv .venv` and use
`.venv/bin/python` in the commands above. The script creates `dist/standalone/shuri.exe` on Windows
or `dist/standalone/shuri` on Linux and macOS, then runs version and CPU smoke tests. CI uploads a
successful native build for each operating system as a workflow artifact.

The executables are unsigned. Windows Smart App Control, macOS Gatekeeper, or other reputation
protection may block an unsigned local build; that is a distribution-trust limitation, not a
diagnostic result. Build from a trusted checkout, retain provenance, and do not bypass organization
policy.

Constraints improve repeatability but do not make builds bit-for-bit identical across operating
systems or toolchains. Dependency updates should be reviewed, constrained, then verified on all CI
platforms.
