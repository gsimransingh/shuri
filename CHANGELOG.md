# Changelog

Notable user-facing changes to Shuri are recorded here.

## 0.7.0 — 2026-10-24

### Changed

- A check that does not apply to the current machine now reports **`N/A` (Not Applicable)** instead of `UNKNOWN`: the Windows-only checks (services, Windows Update, Defender, event logs, physical-drive health) on Linux/macOS, and battery health on a machine with no battery. Not-applicable checks are excluded from coverage and never make a scan "Incomplete", so a Linux, macOS or desktop scan reads as a complete assessment of the checks that apply. `UNKNOWN` now means only a check that applies here but could not get trustworthy evidence. The report schema version is now 6, and the assessment records `not_applicable_checks`.
- The result header names the assessed platform and how many checks are not applicable on it, and coverage is shown over applicable checks.

### Note

This is the first increment of the staged cross-platform direction (see `docs/codebase-review-and-roadmap.md`): it makes a non-Windows scan *honest*, before any native Linux/macOS evidence is added.

## 0.6.0 — 2026-10-19

### Changed

- Simpler command line: `shuri` runs the full check and `shuri check <name>` runs one check. `--details` replaces the `show` word, and `--json PATH` replaces `-f json -o PATH`. The old `shuri doctor` and one-command-per-check names still work for this release but are hidden and print a deprecation note.
- The network check no longer touches the network by default. Its DNS and TCP probes run only with `--probe`, which keeps the default scan fully local and makes the "no telemetry" promise literal. The `SHURI_*` probe overrides apply only with `--probe`.
- A scan with unknown checks now shows "Incomplete — partial score" instead of a bare score such as `100/100`.
- The service check reads state through `psutil` and the `DelayedAutostart` registry flag instead of running and parsing `sc`, so it spawns no processes and no longer depends on command output.
- Diagnostics run on daemon threads with a 45 second per-check and 90 second per-scan deadline. A check that hangs becomes `UNKNOWN` and never blocks the scan or process exit.

### Added

- Exit codes for scripting: `0` all passed, `1` warnings, `2` failures, `3` incomplete (missing evidence). They apply to the full scan and every single check.
- `shuri --debug` prints the traceback of a diagnostic that failed unexpectedly to stderr.
- Each result records the exception class (`error`) when a diagnostic failed or timed out, never the message. The report schema version is now 5.
- `shuri check <name>` validates the name and lists the valid checks on a typo.
- A short "reading the result" guide and a one-line hint after a scan.

### Fixed

- A slow or invalid DNS probe target no longer hangs the network check or crashes it on an invalid host name; the lookup is bounded to 3 seconds.

## 0.5.5 — 2026-10-19

### Security

- Windows tools (`powershell.exe`, `sc.exe`, `powercfg.exe`) now run by absolute path from System32, with System32 as the working directory, so a look-alike program in the current folder or on `PATH` can no longer be launched. Any other program name is refused.
- JSON exports are redacted by default. Redaction is now an allow-list, so a metric that has not been reviewed is hidden instead of leaked, and identifiers are also scrubbed from summaries, findings and score deductions. Use `--raw` to keep identifiers; it prints a warning. `--redact` is accepted but no longer needed.
- Exports no longer overwrite an existing file unless `--force` is given, never follow symbolic links, and are written atomically.
- Added `SECURITY.md`, CodeQL, `pip-audit`, Ruff security rules, commit-pinned GitHub Actions and a hash-locked CI dependency set (`requirements/lock-py312.txt`).

### Changed

- The README now documents the network probes and their `SHURI_*` overrides, and recommends installing a tagged release.
- Removed unused constants left over from the removed report-history feature.

### Fixed

- Services: a stopped on-demand (manual-start) service such as Windows Update or BITS is no longer reported as a fault; only disabled or automatic-start services that are not running are. A service stuck in a starting state is now reported, and delayed-start services are given a grace period after boot. The start type is shown in the details table.
- Defender: the signature timestamp is shown as ISO-8601 instead of the raw PowerShell `/Date(ms)/` value, and detail labels such as "AM Service Enabled" are readable.
- Event logs: bursts of identical events within 60 seconds are counted as one incident. Only storage, file-system and hardware error sources (disk, Ntfs, volmgr, partmgr, storahci, stornvme, Storport, WHEA-Logger) are scored; all other Error-level events are common background noise and are reported in the details (`error_incidents`, per-incident `count` and `high_signal`) without a deduction. The raw `errors` count is kept. The scan window grows from 50 to 200 events, and unexpected `Level` values no longer cause an UNKNOWN result.
- Physical drives: file-backed virtual disks (mounted VHD/VHDX, WSL, Dev Drive) are no longer counted or scored as physical drives; `virtual_drives_ignored` is reported.
- Scoring policy version is now 4 because service and event-log scoring changed.

## 0.5.4 — 2026-08-06

### Changed

- Re-focus Shuri on lightweight Windows workstation readiness.
- Remove report history, comparison, HTML and Markdown output, and automatic process attribution.
- Keep JSON export and explicit redaction for the one supported sharing workflow.
- Reduce CI and standalone delivery to Windows, while retaining portable runtime checks on Linux and macOS.

## 0.5.3 — 2026-08-06

### Added

- Add Linux physical-drive inventory through `lsblk` and optional SMART health through `smartctl`.
- Add macOS physical-drive inventory and built-in SMART status through `diskutil`.
- Preserve trustworthy native unhealthy drive evidence while keeping missing SMART access unknown.
- Exercise installed `shuri` commands and native collectors on Ubuntu, Debian, Fedora, Arch Linux,
  Windows, and macOS in CI.

## 0.5.2 — 2026-08-06

### Added

- Add Linux security posture from available firewall and AppArmor or SELinux controls.
- Add macOS security posture covering Gatekeeper, System Integrity Protection, FileVault, and the
  application firewall.

### Changed

- Generalize the existing `antivirus` report slot to a native Security Posture diagnostic while
  preserving its stable key and stored-report compatibility.

## 0.5.1 — 2026-08-06

### Added

- Add macOS to the complete Python 3.12 verification matrix alongside Windows and Ubuntu.
- Build, smoke-test, and publish native single-file executables for Windows, Linux, and macOS.
- Automatically dispatch services, updates, and recent system logs to Windows, Linux, or macOS
  native read-only collectors.

### Changed

- Promote portable macOS system, CPU, memory, disk, network, and battery checks to supported status.
- Keep platform-native checks explicitly `UNKNOWN` where trustworthy read-only evidence is not yet
  implemented, so missing capabilities do not reduce the health score.

## 0.5.0 — 2026-08-06

### Added

- Add privacy-bounded top-process attribution when CPU utilisation or memory pressure is already
  elevated, limited to five contributors and a bounded collection window.
- Record only process name, process ID, and the relevant CPU or resident-memory value; never request
  command lines, environments, open files, or process memory contents.
- Add readable process tables to `cpu show`, `memory show`, `doctor show`, Markdown, and HTML while
  keeping concise terminal views free of process identity.
- Add report schema 4 with validated optional process-attribution evidence while retaining schema
  0–3 reader compatibility.
- Add deterministic coverage for collection limits, ordering, permission failures, process races,
  healthy-path suppression, scoring isolation, redaction, storage, comparison, and reporters.

### Changed

- Redacted exports now replace process names and IDs while preserving non-identifying resource
  values and the original diagnostic outcome.
- Report comparison deliberately ignores ephemeral process identity and attribution samples.

### Verified

- Healthy CPU and memory results remain free of process-attribution metrics.
- Attribution failures cannot change a warning or failure to healthy and never change deductions.
- The wheel builds and installs in a clean Python 3.12 environment; real Windows integration and
  standalone executable smoke tests pass.

## 0.4.0 — 2026-08-05

### Added

- Add read-only Windows physical-drive health covering model, media/bus type, health and
  operational state, plus optional temperature, wear, error, and power-on counters.
- Add conservative physical-drive scoring under scoring-policy version 2; missing reliability data
  remains `UNKNOWN` and never implies a healthy drive.
- Add bounded four-worker scan execution while sampling CPU alone first to prevent self-induced
  utilisation alerts.
- Add schema version 3 with explicit wall-clock `scan_duration_ms`; schema 0–2 reports remain
  readable and derive compatible legacy timing.
- Add a pinned Python 3.12 dependency graph for development, CI, release, and standalone builds.
- Add weekly Dependabot checks for Python and GitHub Actions dependencies.
- Add a PyInstaller-based single-file Windows build with installed-executable smoke tests and CI
  artifact upload.
- Add progressive terminal disclosure through `shuri <diagnostic> show` and `shuri doctor show`,
  with readable tables for adapters, filesystems, drives, services, Defender, and recent events.
- Retain bounded Windows event metadata (time, severity, ID, and provider) without collecting event
  message bodies.

### Changed

- Replace the slow `Get-NetIPConfiguration` collector with narrower native route and DNS queries.
- Mark incomplete Windows network inventory as a visible, non-scoring warning and expose
  `configuration_complete` in report metrics.
- Record true wall-clock scan duration rather than summing overlapping diagnostic durations.
- Summarize nested terminal metrics in plain language instead of dumping internal JSON objects;
  complete structured evidence remains available in JSON and saved reports.

### Verified

- A real Windows network collection completed with gateway and DNS inventory instead of timing out.
- A real NVMe drive reported a trustworthy healthy Windows state while unsupported optional
  reliability counters remained unavailable.
- Eleven diagnostics completed concurrently without Shuri inflating its own CPU measurement.
- A locally built single-file `shuri.exe` passed version and CPU smoke tests.

## 0.3.0 — 2026-08-02

### Added

- Retain the newest 50 `doctor` assessments in Shuri's per-user application-state directory.
- Add `shuri history` with bounded listing and explicit `--clear --yes` cleanup.
- Add `shuri compare` to show health-score, coverage, and diagnostic-status changes between two
  retained assessments, plus useful hardware and operating-state metric trends.

### Changed

- Centralize package and CLI version metadata on `shuri/version.py`.
- Ignore individually corrupt or oversized history entries so one damaged archive cannot make the
  remaining history unusable.

## 0.2.4 — 2026-08-02

### Fixed

- Parse Microsoft Defender signature timestamps emitted by Windows PowerShell as
  `/Date(milliseconds)/`, including values with timezone suffixes. This ensures stale signature
  age is evaluated instead of silently reported as unavailable.

### Verified

- Run the complete test, lint, formatting, strict typing, wheel-install, and installed-command
  smoke-test workflow on Windows and Ubuntu.
