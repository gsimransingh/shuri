# Process-attribution privacy policy

Shuri 0.5.0 adds bounded process evidence only when the ordinary CPU or memory check has already
produced a `WARNING` or `FAIL`. Attribution is explanatory evidence: it never changes status,
deductions, health score, or coverage, and a healthy result never starts process collection.

## Collection boundary

- At most 2,048 processes are examined within a 750 ms budget.
- At most five contributors are retained, ordered by the relevant resource value.
- CPU attribution uses a bounded 100 ms sample; memory attribution uses resident bytes at one point
  in time.
- Shuri excludes its own process from attribution.
- Exited, protected, inaccessible, and malformed process entries are skipped. The evidence state is
  `partial` or `unavailable`; the original pressure result remains unchanged.

The collector requests only:

- process name;
- process ID;
- CPU percentage for CPU attribution; or
- resident-memory bytes and percentage for memory attribution.

It never requests process command lines, arguments, environment variables, usernames, open-file
paths, network connections, executable paths, process memory contents, or file contents.

## Local, exported, and historical behavior

Local latest and historical reports preserve the bounded identities so the person operating the
workstation can troubleshoot the elevated result. Concise terminal commands report only whether
contributors were captured. Identity appears in `cpu show`, `memory show`, `doctor show`, and
unredacted exports.

`--redact` replaces every process name and process ID with `[redacted]`. Resource values and
evidence state remain so a shared report can still explain the scale of the pressure without naming
the workload. Findings never interpolate process identities.

Historical comparison ignores the complete attribution object. Process IDs are transient and a
process name changing between scans is not treated as a workstation-health trend.

## Schema and failure semantics

Schema 4 validates the attribution resource, state, contributor limit, identity types, non-negative
resource values, collection counts, truncation flag, and duration. Schemas 0–3 remain readable.
Malformed or oversized saved reports remain subject to the ordinary report-rejection policy.
