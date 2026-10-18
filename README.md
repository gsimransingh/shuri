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
pipx install git+https://github.com/gsimransingh/shuri.git@v0.5.5
shuri doctor
```

From a checkout:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
shuri doctor
```

Install a tagged release (as above) rather than the moving `main` branch. `python -m shuri` is
equivalent to the `shuri` command.

## Use

```text
shuri doctor                         # full readiness assessment
shuri doctor show                    # full assessment with detailed evidence
shuri doctor -f json -o report.json  # shareable report; hostname and network IDs are redacted
shuri doctor -f json -o report.json --raw    # keep identifiers (prints a warning)
shuri doctor -f json -o report.json --force  # replace an existing file

shuri cpu | memory | disk | drives | network | battery | system
shuri services | updates | antivirus | eventlogs
shuri network show                   # detailed evidence for one check
shuri version
```

### Exit codes

Every command exits with a code that scripts can act on without parsing the output:

| Code | Meaning |
| --- | --- |
| `0` | Every check passed. |
| `1` | At least one warning; nothing failed and no evidence was missing. |
| `2` | At least one check failed. |
| `3` | Evidence was missing (a check was `UNKNOWN`) and nothing failed, so readiness cannot be confirmed. |

Command-line usage errors (a bad option, an existing export file) also exit with `2`, but they
print an `Error` panel to stderr instead of a report. When a score is incomplete, `doctor` shows
"Incomplete — partial score" instead of presenting it as a full result.

Each check is bounded to 45 seconds and a whole scan to 90 seconds; a check that runs over becomes
`UNKNOWN` instead of hanging. If a check fails unexpectedly, run `shuri --debug doctor` to print its
traceback to stderr (tracebacks can contain file paths, so review them before sharing).

`doctor` does not retain local history. A JSON export is created only when you request one, and
Shuri never overwrites an existing file unless you pass `--force`.

## Privacy and network use

Shuri collects only the evidence needed for the checks. It does not collect file contents,
passwords, browser history, command lines, environments, or memory contents. It has no telemetry
and sends no data anywhere.

The network check makes two small probes: a DNS lookup of `example.com` and a TCP connection to
`1.1.1.1:443`. Nothing is sent over the connection. To probe your own targets instead, set
`SHURI_DNS_PROBE_HOST`, `SHURI_CONNECTIVITY_HOST` and `SHURI_CONNECTIVITY_PORT` before running.

JSON exports are redacted by default: hostname, IP and MAC addresses, DNS servers, adapter names
and probe targets are removed, and anything Shuri has not explicitly reviewed is hidden too. Use
`--raw` only for your own records, and review every exported report before sharing it.

To report a security problem, see [SECURITY.md](SECURITY.md).

## Development

```powershell
python -m pip install --require-hashes -r requirements/lock-py312.txt
python -m pip install --no-deps --no-build-isolation -e .
python scripts/verify.py
```

See the [architecture](docs/architecture.md), [support matrix](docs/support-matrix.md), and
[physical-drive policy](docs/physical-drive-health.md).

## License

MIT. See [LICENSE](LICENSE).
