# Shuri

**Shuri** is a fast, open-source workstation diagnostics CLI for IT support,
systems, and security teams. It answers one practical question: _what is the
health of this workstation right now?_

It is a portable first-response toolkit, not a monitoring agent, SIEM, RMM,
EDR, or antivirus product.

## What it checks

- CPU utilisation, core count, frequency, and system load when available
- Memory and swap pressure
- Disk capacity and free space
- Network adapters, MAC addresses, default gateway, DNS configuration, and reachability
- Battery charge plus capacity health on supported Windows laptops
- Operating-system metadata and uptime
- Key Windows services, pending reboot/update state, antivirus posture, and recent event-log activity

Every deduction in the health score is shown in the report.
The report also shows the exact calculation: `100 - total deductions = health score`.

## Install

Shuri requires Python 3.12 or later.

### Install as a system command

The command is named `shuri`, while the distribution is deliberately named
`shuri-cli` to avoid conflicts with unrelated Python packages. Install it with
[`pipx`](https://pipx.pypa.io/) so it is available from any folder without
mixing its dependencies into your system Python:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
# Open a new PowerShell window, then run:
pipx install git+https://github.com/gsimransingh/shuri.git
shuri doctor
```

### Install from a clone

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
shuri doctor
```

Using a virtual environment keeps Shuri and its `shuri` command isolated from other Python
installations on the workstation.

For contributors:

```text
python -m pip install -e ".[dev]"
python scripts/verify.py
```

The verification command runs tests, linting, formatting, strict typing, builds the wheel, installs
it into a temporary clean environment, and smoke-tests the installed `shuri` command. Package
installation requires network access when dependencies are not already available in pip's cache.

## Usage

```text
shuri scan                         # all diagnostics
shuri doctor                       # diagnostics plus health score
shuri doctor -f html -o report.html
shuri doctor -f json -o report.json
shuri doctor -f json --redact -o report-to-share.json
shuri doctor -f markdown
shuri cpu                          # one diagnostic
shuri network
shuri system-info                  # OS and workstation information
shuri report --format html         # export the last saved assessment
shuri version
```

From a source checkout, `python -m shuri system-info` runs the local code directly.

Shuri is cross-platform where possible. Windows-specific checks gracefully
report as unavailable on other platforms instead of treating that as a fault.
Windows capacity, update, and antivirus checks use native Windows data when available;
an unavailable data source is reported as unknown rather than scored as a failure.
See the [platform support matrix](docs/support-matrix.md) for the exact per-check contract and the
[report-schema policy](docs/report-schema.md) for stored-report compatibility.

Full scans show live progress, and reports include the duration of each diagnostic. The latest
local report is written atomically to Shuri's per-user application-state directory, so
`shuri report` works consistently from any folder. A legacy report in the checkout's `.shuri`
folder is copied to the new location the first time it is loaded.

## Network probes

DNS resolution and TCP connectivity are reported as separate probes. A failed probe is evidence
about that target, not a definitive claim that the internet is unavailable. Organizations can
provide their own targets with `SHURI_DNS_PROBE_HOST`, `SHURI_CONNECTIVITY_HOST`, and
`SHURI_CONNECTIVITY_PORT` environment variables. The port must be between 1 and 65535.

## Privacy and sharing

Local saved reports remain complete so support diagnostics retain their evidence. Before sharing
an export, pass `--redact`. Redacted exports replace the report and metric hostnames, gateways,
probe targets, usernames, and MAC addresses, and remove collected IP-address and DNS-server lists.
They retain health status, timings, hardware facts, deductions, and non-identifying service and
security state. Shuri does not collect file contents, passwords, browser history, or command-line
contents. Review every report before sharing it because organization-specific check output may
still be sensitive.

## Health score

The score starts at 100. Checks make explicit, bounded deductions; for example,
very low system-drive space subtracts 15 points, and a pending reboot subtracts
5. The final label is:

| Score | Assessment |
| --- | --- |
| 90–100 | Excellent |
| 75–89 | Healthy |
| 60–74 | Needs Attention |
| 40–59 | Poor |
| 0–39 | Critical |

## Project layout

```text
├── shuri/
│   ├── checks/       # small, independent diagnostics
│   ├── core/         # check registry, runner, and scoring
│   ├── models/       # typed report data
│   ├── reporters/    # terminal, JSON, HTML, and Markdown output
│   └── utils/        # platform and filesystem helpers
└── scripts/          # contributor and release verification
```

## License

MIT. See [LICENSE](LICENSE).
