# Development and Windows standalone builds

The Python 3.12 dependency set used by CI and release verification is pinned in
`requirements/constraints-py312.txt`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements\constraints-py312.txt -e ".[dev]"
.\.venv\Scripts\python.exe scripts\verify.py
```

To build the Windows standalone executable:

```powershell
.\.venv\Scripts\python.exe -m pip install -c requirements\constraints-py312.txt -e ".[standalone]"
.\.venv\Scripts\python.exe scripts\build_standalone.py
.\dist\standalone\shuri.exe doctor
```

The executable is unsigned. Build from a trusted checkout and follow organization policy before
deployment.
