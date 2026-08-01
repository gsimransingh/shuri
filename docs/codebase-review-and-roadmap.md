# Shuri codebase review and roadmap

Reviewed: 2026-08-01 (Shuri 0.2.0)

## Executive summary

Shuri has a strong small-project foundation: diagnostics are independent, results are typed,
scoring is explainable, output is separated from collection, and a failed check cannot abort a
full scan. The current code is suitable for an alpha and is easy to extend.

The next milestone should focus on trustworthiness rather than adding many checks. In particular,
Shuri needs to distinguish a healthy machine from an incomplete assessment, harden saved-report
storage and schema handling, test the Windows paths on Windows, and make potentially sensitive
report data explicit. After that, check accuracy and packaging can be expanded confidently.

## Current structure

The runtime flow is:

1. `shuri.cli` selects a command and builds a report.
2. `shuri.core.registry` creates the ordered set of diagnostics.
3. `shuri.core.runner` executes each check independently and converts unexpected failures to
   `UNKNOWN` results.
4. Files under `shuri.checks` collect and assess individual concerns.
5. `shuri.core.scoring` combines explicit deductions into a score.
6. `shuri.models.report` provides the shared result/report contract.
7. Files under `shuri.reporters` present the same report as terminal, JSON, Markdown, or HTML.
8. `shuri.core.storage` saves the latest report for later export.

Supporting platform commands are isolated in `shuri.utils.platform`. Pure builder functions for
CPU, memory, and disk make their threshold logic directly testable.

## Strengths

- **Clear boundaries.** Collection, orchestration, scoring, persistence, and presentation are
  separate. Checks do not print, and reporters do not recalculate health.
- **Fault isolation.** One broken or unsupported diagnostic becomes `UNKNOWN` instead of taking
  down the scan.
- **Transparent scoring.** Every deduction has points, a reason, and a source check; all report
  formats expose the calculation.
- **Immutable typed contracts.** Frozen, slotted dataclasses and `CheckStatus` make the internal
  API small and predictable.
- **Safe command execution.** External commands use argument sequences, timeouts, captured output,
  and no shell invocation. PowerShell usage is read-only.
- **Graceful platform degradation.** Windows-only checks return unknown on unsupported platforms
  rather than falsely failing the workstation.
- **Multiple useful outputs.** Human-readable terminal/Markdown/HTML and machine-readable JSON all
  originate from one report model.
- **Good extension point.** A no-argument check plus one registry entry is enough to add a basic
  diagnostic.
- **Baseline engineering automation.** Ruff, Black, mypy strict mode, pytest, and an Ubuntu CI job
  are configured. Generated environments, caches, reports, and local state are ignored by Git.

## Weaknesses and risks

### P0: assessment correctness and trust

1. **Incomplete scans can still score 100/100.** Unknown checks make no deduction and there is no
   coverage/confidence field. A machine where every privileged Windows query failed can be called
   “Excellent.” The numeric score must be paired with assessment completeness, and labels should
   not imply confidence that was not earned.
2. **The score policy is distributed through check implementations.** Threshold constants cover
   only CPU, memory, and disk; deduction weights and other thresholds are embedded in many files.
   This makes policy review, calibration, versioning, and customer-specific profiles difficult.
3. **Report data has no schema version.** `report_from_dict` assumes required keys and enum values
   exist. A future model change or damaged cache can break `shuri report` with an unhandled error.

### P1: reliability and product behavior

4. **Latest-report storage depends on the current directory.** A scan run in one folder cannot be
   exported from another. Installing Shuri as a system command makes this surprising. Use a stable
   per-user application-data location, with an optional explicit path.
5. **Saved reports are not written atomically or recovered defensively.** Interruption during a
   write, malformed JSON, permission errors, or incompatible data can crash the command. Write a
   temporary file then replace, validate on load, and show a concise recovery message.
6. **Full scans are sequential.** Several independent operations have 5–20 second timeouts, so one
   unavailable Windows subsystem can make a scan feel stalled. Add progress feedback first; then
   consider bounded concurrency for independent I/O checks.
7. **Connectivity semantics are too narrow.** A TCP connection to `1.1.1.1:53` may be blocked on an
   otherwise working corporate network. DNS and one external endpoint should be reported as probes,
   not treated as definitive internet failure; endpoints should be configurable.
8. **Event-log counting is fragile.** It parses localized text and requests at most 50 events, so
   counts can be language-dependent and undercount busy systems. Query structured XML and clearly
   report truncation or request aggregate counts.
9. **Some platform errors lose diagnostic detail.** Command wrappers collapse timeout, missing
   executable, access denied, non-zero exit, and empty output into `None`. Users see “could not be
   queried” without knowing whether elevation, policy, or availability is responsible.
10. **No explicit privacy/redaction policy.** Reports can contain hostname, IP and MAC addresses,
    gateways, DNS configuration, OS details, service state, and security-product data. Add a warning,
    document intended handling, and provide a redacted/share-safe export mode.

### P2: maintainability and delivery

11. **Tests concentrate on pure happy-path logic.** Missing coverage includes runner exception
    isolation, registry errors, storage round-trips/corruption, CLI error paths, reporter escaping,
    command timeout/error classification, and most Windows checks.
12. **CI runs only on Ubuntu.** The most differentiated diagnostics are Windows-specific, yet they
    are not executed in a Windows CI job. Add a Windows matrix entry and mock subprocess boundaries
    for deterministic tests.
13. **Local setup is easy to leave half-configured.** During this review, both local virtual
    environments and the system Python lacked pytest/Ruff/Black/mypy, so the declared verification
    suite could not be executed. Add a bootstrap task and a single `verify` command, and document how
    to confirm that the development extras are installed.
14. **Supported platform messaging is inconsistent.** Packaging says “OS Independent,” while much
    of the product value and README detail is Windows-specific. Publish an explicit support matrix
    per check and distinguish “supported,” “best effort,” and “unavailable.”
15. **Dependency ranges have no upper bounds or lock/constraints strategy.** Reproducibility may
    drift over time. Keep broad runtime metadata if desired, but use a tested constraints or lock
    file for development and releases.
16. **Version defaults are duplicated.** Package metadata, `Report.shuri_version`, and the storage
    fallback can diverge (the fallback is still `0.1.0`). Use one version source and treat report
    schema version separately from application version.
17. **The reporter implementations duplicate formatting rules.** Byte formatting and complex-value
    display differ across terminal, Markdown, and HTML. Establish normalized display helpers and
    escaping tests so formats do not silently disagree.

## Recommended fixes

### Milestone 1 — trustworthy assessments

- Add `schema_version`, `completed_checks`, `unknown_checks`, and `coverage_percent` to reports.
- Define a label policy for incomplete assessments (for example, “100/100 — incomplete, 6/10
  checks completed”) and test it at every boundary.
- Move scoring weights and thresholds into a typed, versioned policy module; reject negative points
  when constructing a deduction instead of only ignoring them during totals.
- Make report loading validate data and handle corrupt/incompatible caches without a traceback.
- Centralize the application and schema versions.

**Exit criteria:** a 100 score cannot be mistaken for a complete clean bill of health; old, corrupt,
and unsupported saved reports produce an actionable message; scoring policy has focused tests.

### Milestone 2 — reliable daily use

- Store the latest report in the platform-appropriate per-user data directory and write atomically.
- Add scan progress and show duration; evaluate bounded concurrency after measuring typical runs.
- Return structured command failures (`timeout`, `not_found`, `access_denied`, `exit_code`) while
  keeping raw command details out of normal reports.
- Replace event-log text parsing with structured output and expose truncation.
- Rework network checks as separately named probes and allow organization-specific endpoints.
- Add `--redact` (or a share-safe default) and document exactly which fields it removes.

**Exit criteria:** commands behave consistently from any folder, failures explain the next action,
and exported reports have an intentional privacy posture.

**Completed 2026-08-01:** latest-report storage now uses an atomic per-user path with legacy
migration; command failures are classified without exposing raw command details; scans show
progress and per-check duration; DNS and TCP probes are separate and configurable; event-log data
is structured and reports truncation; and exports support explicit share-safe redaction. A real
Windows scan completed all 10 checks in 21.1 seconds. Windows Update dominated at 13.1 seconds, so
execution remains sequential to avoid adding concurrency complexity before it is necessary.

### Milestone 3 — test and release confidence

- Add unit tests for registry, runner, storage, CLI validation, all status branches, and escaping.
- Run CI on Windows and Ubuntu with Python 3.12; keep Windows commands mocked in unit tests and add a
  small opt-in integration suite for a real Windows runner.
- Provide one contributor bootstrap path and one verification command covering tests, lint, format,
  and typing.
- Add packaging smoke tests: build wheel, install into a clean environment, run `shuri version` and
  a non-privileged command.
- Publish the check/platform support matrix and report-schema compatibility policy.

**Exit criteria:** the same clean verification succeeds locally and in both CI environments, and a
built wheel is tested before release.

**Implemented locally 2026-08-01:** focused registry, runner-isolation, storage-validation,
CLI-error, status-outcome, and reporter-escaping tests are in place. `python scripts/verify.py`
runs the complete quality suite, builds a wheel, installs it with dependencies into a temporary
clean environment, and smoke-tests the installed CLI. CI now uses that command on Windows and
Ubuntu, with an additional opt-in read-only Windows integration check. Platform support and schema
compatibility contracts are published. The remaining exit check is the first successful remote CI
matrix run after these changes are pushed.

### Milestone 4 — capability expansion

Only after the trust/reliability milestones, consider process-level CPU/memory attribution, disk
SMART/health where safely available, richer update age/history, configurable service policies,
trend comparison between reports, and organization-specific scoring profiles.

## Immediate next steps

1. Push the Milestone 3 changes and confirm both Windows and Ubuntu verification jobs pass.
2. Treat any matrix-only failure as a release blocker and reproduce it locally where practical.
3. After the matrix is green, choose the next patch version and complete the release checklist.

## Verification note

The original review found an incomplete local environment. The repository `venv` is now usable,
and the complete Milestone 3 verifier passes locally on Windows with Python 3.12, including the
clean wheel-install smoke test and the opt-in native integration check.
