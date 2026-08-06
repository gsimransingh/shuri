# Development verification

The Python 3.12 dependency set used by CI and release verification is pinned in
`requirements/constraints-py312.txt`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements\constraints-py312.txt -e ".[dev]"
.\.venv\Scripts\python.exe scripts\verify.py
```
