# Architecture

Shuri keeps the path from collection to output short:

1. Each function in `shuri.checks` collects one read-only signal and returns a typed `CheckResult`.
2. `DiagnosticRunner` samples CPU first, then runs the remaining checks in a bounded worker pool.
3. `assess_health` calculates the score from explicit deductions.
4. Terminal output renders a concise result; `show` renders structured detail; JSON is optional export.

Windows native checks use narrow PowerShell calls behind `shuri.utils.platform`. They must return
`UNKNOWN`, rather than guessing, when trustworthy evidence is unavailable. Linux and macOS use the
portable checks only; Windows-specific checks intentionally remain unavailable on those platforms.

There is no report database, history, comparison engine, HTML renderer, background process, or
configuration layer. New checks should earn their place by answering a workstation-readiness question
that support staff can act on.
