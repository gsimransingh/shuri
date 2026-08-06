# Changelog

Notable user-facing changes to Shuri are recorded here.

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
