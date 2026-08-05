# Architecture

Shuri separates collection, assessment, storage, and presentation.

1. A diagnostic in `shuri.checks` collects one concern and returns a typed `CheckResult`. It never
   prints.
2. `DiagnosticRunner` samples CPU serially, then executes independent checks in a bounded worker
   pool. Registry order is preserved and one unavailable check cannot prevent an assessment.
3. `assess_health` turns transparent deductions into a `HealthAssessment`.
4. Storage atomically writes the latest report and retains the newest 50 assessed reports.
5. `compare_reports` derives score, coverage, and status changes without modifying reports.
6. Reporters render reports and comparisons without changing their data.

The CLI records assessment wall time separately from diagnostic durations. Parallel durations
overlap, so adding them would not describe user-visible time. CPU runs before heavier collectors so
Shuri's own PowerShell and Python work does not create a misleading utilisation alert.

To add a check, implement a no-argument function returning `CheckResult`, then add it to
`default_registry()` in `shuri.core.registry`. Keep platform calls behind `shuri.utils.platform` and
return `UNKNOWN` when the platform does not support the check.

Physical-drive collection uses read-only Windows storage interfaces. Explicit native unhealthy
states can affect scoring; absent counters, unsupported controllers, and ambiguous states remain
unknown. The model deliberately omits serial numbers.

Terminal presentation uses progressive disclosure. A diagnostic command provides a compact health
view; its `show` action renders already-collected structured evidence as purpose-built tables.
Event-log detail is bounded to severity, timestamp, identifier, and provider and excludes message
bodies. JSON remains the complete machine-readable representation.

CPU and memory checks add process attribution only after their ordinary assessment is already
`WARNING` or `FAIL`. The collector is bounded by process count, elapsed time, and five output rows.
It excludes Shuri's own process and requests only name, ID, and the relevant resource counter.
Access-denied, exited, and protected processes make evidence partial or unavailable without changing
the pressure status or deductions. Concise terminal views summarize availability without printing
process identity; detailed and exported views render the bounded evidence.

Platform commands return a structured `CommandResult`. Checks translate stable failure categories
with `command_failure_message`; raw commands, stdout, and stderr are not copied into findings.
Exports pass through `shuri.core.privacy` only when redaction is explicitly requested, leaving the
complete locally saved report unchanged. Process names and IDs are replaced in redacted exports;
resource values remain available for troubleshooting.

History files use the report schema and UTC generation time. The latest report remains independent,
so clearing history does not break `shuri report`. Damaged history entries are skipped individually;
latest-report corruption remains an actionable error for the command addressing that artifact.
