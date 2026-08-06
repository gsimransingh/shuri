# Shuri

Shuri is a fast, read-only CLI that answers one question: **is this Windows workstation ready to work?**

It is designed for first-response support: no agent, account, background service, or telemetry.
Shuri is intentionally small. It is not an RMM, monitoring platform, SIEM, EDR, or antivirus product.

## What it checks

- CPU, memory, disk space, physical-drive health, network, battery, and operating-system basics
- Windows services, Windows Update state, Microsoft Defender, and recent Windows system events
- A transparent health score with every deduction shown

Windows is the supported and continuously tested platform. Linux and macOS can run portable checks,
but Windows-native readiness checks report `UNKNOWN` there and do not affect the score.

## Install

Shuri requires Python 3.12 or newer. Install it with `pipx` to make `shuri` available everywhere:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
# Open a new PowerShell window, then run:
pipx install git+https://github.com/gsimransingh/shuri.git
shuri doctor
```

From a checkout:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
shuri doctor
```

Always use the installed `shuri` command, not `python -m main.py`.

## Use

```text
shuri doctor                         # full readiness assessment
shuri doctor show                    # full assessment with detailed evidence
shuri doctor -f json -o report.json  # shareable machine-readable report
shuri doctor -f json --redact -o report.json

shuri cpu | memory | disk | drives | network | battery | system
shuri services | updates | antivirus | eventlogs
shuri network show                   # detailed evidence for one check
shuri version
```

`doctor` does not retain local history. A JSON export is created only when you request one.

## Standalone Windows executable

Build a local `shuri.exe` without requiring Python on the target workstation:

```powershell
.\.venv\Scripts\python.exe -m pip install -c requirements\constraints-py312.txt -e ".[standalone]"
.\.venv\Scripts\python.exe scripts\build_standalone.py
.\dist\standalone\shuri.exe doctor
```

The executable is unsigned; follow your organization’s software-trust policy.

## Privacy

Shuri collects only the evidence needed for the checks. It does not collect file contents,
passwords, browser history, command lines, environments, or memory contents. Use `--redact` before
sharing JSON externally; review every exported report first.

## Development

```powershell
python -m pip install -c requirements/constraints-py312.txt -e ".[dev]"
python scripts/verify.py
```

See the [architecture](docs/architecture.md), [support matrix](docs/support-matrix.md), and
[physical-drive policy](docs/physical-drive-health.md).

## License

MIT. See [LICENSE](LICENSE).
