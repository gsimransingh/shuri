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
- Network adapters, name resolution, and internet reachability
- Battery condition on supported laptops
- Operating-system metadata and uptime
- Key Windows services, pending reboot state, Defender, and recent event-log activity

Every deduction in the health score is shown in the report.

## Install

Shuri requires Python 3.12 or later.

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
shuri doctor --html --output report.html
shuri doctor --json --output report.json
shuri doctor --markdown
shuri cpu                          # one diagnostic
shuri network
shuri report --format html         # export the last saved assessment
shuri version
```

Shuri is cross-platform where possible. Windows-specific checks gracefully
report as unavailable on other platforms instead of treating that as a fault.

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
