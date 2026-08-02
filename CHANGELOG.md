# Changelog

Notable user-facing changes to Shuri are recorded here.

## 0.2.4 — 2026-08-02

### Fixed

- Parse Microsoft Defender signature timestamps emitted by Windows PowerShell as
  `/Date(milliseconds)/`, including values with timezone suffixes. This ensures stale signature
  age is evaluated instead of silently reported as unavailable.

### Verified

- Run the complete test, lint, formatting, strict typing, wheel-install, and installed-command
  smoke-test workflow on Windows and Ubuntu.
