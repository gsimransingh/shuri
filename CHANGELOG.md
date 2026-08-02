# Changelog

Notable user-facing changes to Shuri are recorded here.

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
