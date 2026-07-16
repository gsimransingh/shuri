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
# Open a new PowerShell window, then replace YOUR_USERNAME.
pipx install git+https://github.com/YOUR_USERNAME/shuri.git
shuri doctor
```

### Install from a clone

```powershell
python -m pip install .
shuri doctor
```

For contributors:

```powershell
python -m pip install -e ".[dev]"
pytest
ruff check .
black --check .
```

## Usage

```text
shuri scan                         # all diagnostics
shuri doctor                       # diagnostics plus health score
shuri doctor -f html -o report.html
shuri doctor -f json -o report.json
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
shuri/
├── checks/       # small, independent diagnostics
├── core/         # check registry, runner, and scoring
├── models/       # typed report data
├── reporters/    # terminal, JSON, HTML, and Markdown output
└── utils/        # platform and filesystem helpers
```

## License

MIT. See [LICENSE](LICENSE).
