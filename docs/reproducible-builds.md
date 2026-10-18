# Development verification

CI and local verification install a **hash-locked** dependency set, so a tampered or substituted
package fails the install instead of running. `requirements/lock-py312.txt` pins every package and
its SHA-256 hashes. `requirements/constraints-py312.txt` lists the tested direct versions and is
used when the built wheel is smoke-tested.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements\lock-py312.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe scripts\verify.py
```

## Updating the lock

Regenerate it after changing dependencies in `pyproject.toml` or bumping
`constraints-py312.txt` (Dependabot does the latter):

```powershell
py -3.12 -m pip install pip-tools
py -3.12 -m piptools compile pyproject.toml --extra dev --generate-hashes --allow-unsafe `
  --no-strip-extras -c requirements\constraints-py312.txt -o requirements\lock-py312.txt
```

Then run `scripts\verify.py` and commit both files together.
