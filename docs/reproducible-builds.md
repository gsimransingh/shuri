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

## Build the Windows executable

```powershell
.\.venv\Scripts\python.exe -m pip install -c requirements\constraints-py312.txt -e ".[standalone]"
.\.venv\Scripts\python.exe scripts\build_standalone.py
.\dist\standalone\shuri.exe doctor
```

The script creates `dist/standalone/shuri.exe`, then runs version and CPU smoke tests. CI uploads a
successful Windows build as a workflow artifact.

The executable is unsigned. Smart App Control or reputation protection may block an unsigned local
build; that is a distribution-trust limitation, not a diagnostic result. Build from a trusted
checkout, retain provenance, and do not bypass organization policy.

Constraints improve repeatability but do not make builds bit-for-bit identical across operating
systems or toolchains. Dependency updates should be reviewed, constrained, then verified on both CI
platforms.
