# Shuri

**Shuri** is a fast, open-source workstation diagnostics CLI for IT support,
systems, and security teams. It answers one practical question: _what is the
health of this workstation right now?_

It is a portable first-response toolkit, not a monitoring agent, SIEM, RMM,
EDR, or antivirus product.

## What it checks

- CPU utilisation, core count, frequency, and system load when available, with bounded top-process
  attribution only when utilisation is elevated
- Memory and swap pressure, with bounded top-process attribution only when pressure is detected
- Disk capacity and free space
- Physical-drive inventory and native health evidence when exposed by the operating system
- Network adapters, MAC addresses, default gateway, DNS configuration, and reachability
- Battery charge plus capacity health on supported Windows laptops
- Operating-system metadata and uptime
- Native system services, pending restart/update state, security posture, and recent system-log activity

System, CPU, memory, filesystem, network, battery, service, update, security, log, and drive checks
automatically select native Windows, Linux, or macOS evidence. A check reports `UNKNOWN` without a
score penalty only when trustworthy evidence cannot be obtained.

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

### Build a standalone executable

The standalone build does not require Python on the target workstation. Build it on the target
operating system from a trusted checkout; the executable is written to `dist/standalone/shuri.exe`
on Windows or `dist/standalone/shuri` on Linux and macOS:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements\constraints-py312.txt -e ".[standalone]"
.\.venv\Scripts\python.exe scripts\build_standalone.py
```

On Linux and macOS, use `python3 -m venv .venv` and `.venv/bin/python` in the same commands. The
build script creates a native single-file executable and smoke-tests its `version` and `cpu`
commands. CI publishes builds for Windows, Linux, and macOS as workflow artifacts. Release binaries
are not yet code-signed; review the source and verify provenance before deployment.

For contributors:

```text
python -m pip install -c requirements/constraints-py312.txt -e ".[dev]"
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
shuri cpu show                     # top CPU contributors when utilisation is elevated
shuri memory show                  # top memory contributors when pressure is detected
shuri disk show                    # every detected filesystem
shuri drives                       # physical-drive reliability
shuri drives show                  # detailed physical-drive evidence
shuri network
shuri network show                 # adapters, probes, and configuration
shuri services show                # native monitored service states
shuri antivirus show               # native security posture
shuri eventlogs show               # recent native system-log metadata
shuri doctor show                  # expanded evidence for a full assessment
shuri system-info                  # OS and workstation information
shuri report --format html         # export the last saved assessment
shuri history                      # list retained reports, newest first
shuri compare                      # compare the two newest assessments
shuri compare --older 4 --newer 2  # compare selected history entries
shuri history --clear --yes        # clear history but retain the latest report
shuri version
```

After installation, always invoke Shuri through the `shuri` command, including from a source
checkout: `shuri system-info`.

### Concise and detailed views

Diagnostic commands use progressive disclosure. Run the command by itself for a quick health
overview, then add `show` when troubleshooting requires the collected evidence:

| Command | Detailed evidence |
| --- | --- |
| `shuri cpu show` | Up to five top CPU contributors after an elevated CPU result |
| `shuri memory show` | Up to five top resident-memory contributors after memory pressure |
| `shuri disk show` | Detected filesystems, capacity, free space, and usage |
| `shuri drives show` | Physical-drive model, type, bus, health, size, temperature, and wear |
| `shuri network show` | DNS/TCP probes and detected adapters with state and addresses |
| `shuri services show` | Important native services and their current state |
| `shuri antivirus show` | Defender on Windows or native Linux/macOS security controls |
| `shuri eventlogs show` | Up to 50 recent native system events with metadata but no message body |
| `shuri doctor show` | Structured evidence from every check in one assessment |

Process attribution is collected only after CPU or memory is already elevated. It is bounded to
five contributors and records only process name, process ID, and the relevant CPU or resident-memory
value. It never requests command lines, environment variables, open files, or process memory
contents. Event message bodies are also deliberately excluded because they can contain usernames,
file paths, and other workstation-specific data. `services show` covers Shuri's monitored native
service set rather than inventorying every installed service. JSON exports remain the complete
machine-readable representation of the evidence Shuri collects.

Shuri automatically detects Windows, Linux, or macOS and routes each diagnostic to native read-only
collectors. Windows uses SCM, Windows Update, Defender, Event Log, and Storage Management; Linux
uses systemd, a detected package manager, native security controls, journald, `lsblk`, and optional
SMART evidence; macOS uses launchd, Software Update, platform security controls, unified logging,
and `diskutil`. An unavailable data source is reported as unknown rather than scored as a failure.
See the [platform support matrix](docs/support-matrix.md),
[process-attribution privacy policy](docs/process-attribution.md),
[physical-drive policy](docs/physical-drive-health.md),
[reproducible build guide](docs/reproducible-builds.md), and
[report-schema policy](docs/report-schema.md).

Full scans show live progress. CPU is sampled before Shuri starts its heavier collectors, then the
remaining independent diagnostics run through a bounded four-worker pool. Reports include each
diagnostic's duration and the actual wall-clock scan duration. The latest
local report is written atomically to Shuri's per-user application-state directory, so
`shuri report` works consistently from any folder. A legacy report in the checkout's `.shuri`
folder is copied to the new location the first time it is loaded. Each `doctor` assessment is also
retained in local history; Shuri automatically keeps the newest 50 assessments. `shuri compare`
shows score, coverage, diagnostic-status changes, and useful CPU, memory, battery, disk, update,
and event-log metric trends.

## Network probes

DNS resolution and TCP connectivity are reported as separate probes. A failed probe is evidence
about that target, not a definitive claim that the internet is unavailable. Organizations can
provide their own targets with `SHURI_DNS_PROBE_HOST`, `SHURI_CONNECTIVITY_HOST`, and
`SHURI_CONNECTIVITY_PORT` environment variables. The port must be between 1 and 65535.

## Privacy and sharing

Local latest and historical reports remain complete so support diagnostics retain their evidence.
They never leave the workstation unless the user exports or otherwise shares them. Before sharing
an export, pass `--redact`. Redacted exports replace the report and metric hostnames, gateways,
probe targets, usernames, MAC addresses, process names, and process IDs, and remove collected
IP-address and DNS-server lists. They retain process resource values, health status, timings,
hardware facts, deductions, and non-identifying service and security state. Shuri does not collect
file contents, passwords, browser history, process command lines, environments, open-file paths, or
memory contents. Physical-drive reports include model, type, capacity, and reliability state but do
not request serial numbers. Review every report before sharing it because organization-specific
check output may still be sensitive.

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

## Roadmap

Shuri 0.5.0 adds privacy-bounded CPU and memory attribution without changing healthy results or
scoring. The next planned milestone focuses on organization policy: configurable service and
network targets plus named scoring profiles. See the
[current roadmap](docs/codebase-review-and-roadmap.md) for scope, exit criteria, limitations, and
later candidates.

## License

MIT. See [LICENSE](LICENSE).
