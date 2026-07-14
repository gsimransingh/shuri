# Architecture

Shuri separates collection, assessment, and presentation.

1. A diagnostic in `shuri.checks` collects one concern and returns a typed
   `CheckResult`. It never prints.
2. The `DiagnosticRunner` executes checks independently. One unavailable check
   cannot prevent a workstation assessment.
3. `assess_health` turns transparent check deductions into a `HealthAssessment`.
4. Reporters render the resulting `Report` without changing its data.

To add a check, implement a no-argument function returning `CheckResult`, then
add it to `default_registry()` in `shuri.core.registry`. Keep platform-specific
calls behind `shuri.utils.platform` and return `UNKNOWN` when the platform does
not support a check.
