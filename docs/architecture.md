# Architecture

Shuri separates collection, assessment, and presentation.

1. A diagnostic in `shuri.checks` collects one concern and returns a typed
   `CheckResult`. It never prints.
2. The `DiagnosticRunner` executes checks independently. One unavailable check
   cannot prevent a workstation assessment.
3. `assess_health` turns transparent check deductions into a `HealthAssessment`.
4. Storage atomically writes the latest report and retains the newest 50 assessed reports.
5. `compare_reports` derives score, coverage, and check-status changes without modifying reports.
6. Reporters render reports and comparisons without changing their data.

To add a check, implement a no-argument function returning `CheckResult`, then
add it to `default_registry()` in `shuri.core.registry`. Keep platform-specific
calls behind `shuri.utils.platform` and return `UNKNOWN` when the platform does
not support a check.

Platform commands return a structured `CommandResult`. Checks translate its stable failure
category into safe, actionable language with `command_failure_message`; raw commands, stdout, and
stderr are not copied into normal findings. Exports pass through `shuri.core.privacy` only when the
user explicitly requests redaction, leaving the complete locally saved report unchanged.

History files use the existing report schema and are ordered by their UTC generation timestamp.
The latest-report file remains independent so clearing history does not break `shuri report`.
Damaged history entries are skipped individually, while latest-report corruption remains an
actionable error because that command addresses one specific saved artifact.
