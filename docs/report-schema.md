# Report schema compatibility

Shuri application versions, report-schema versions, and scoring-policy versions are independent.
The current values in Shuri 0.5.0 are:

| Contract | Version | Purpose |
| --- | ---: | --- |
| Application | 0.5.0 | CLI and package release |
| Report schema | 4 | Stored and exported report structure |
| Scoring policy | 2 | Thresholds and deduction weights |

## Reader compatibility

Shuri 0.5.0 reads report schemas 0, 1, 2, 3, and 4:

- **Schema 0:** legacy reports without an explicit `schema_version`.
- **Schema 1:** adds coverage and policy metadata.
- **Schema 2:** adds the explicit top-level `redacted` state.
- **Schema 3:** adds top-level `scan_duration_ms`, the measured wall-clock assessment duration.
- **Schema 4:** adds validated optional `process_attribution` metrics to elevated CPU and memory
  results. Healthy results do not contain the field.

Older reports are normalized in memory to schema 4. Their scan duration is derived from the sum of
diagnostic durations because a true wall-clock measurement was not recorded. When a legacy latest
report is found in the former workspace-local location, Shuri validates it and writes the
normalized copy to the current per-user location. The original is not deleted.

Reports with an unknown future schema are rejected instead of being partially interpreted. Corrupt
JSON, invalid enums, missing required fields, invalid field types, and negative durations are also
rejected. Reports larger than 10 MiB are rejected before parsing. Shuri writes only the current
schema.

## Compatibility policy

- A field whose meaning affects consumers requires a schema-version increment.
- Removing, renaming, or changing a field requires an increment and migration or rejection path.
- Scoring changes increment `policy_version` independently.
- Application releases do not automatically increment either contract.
- Old-schema support may be removed only after a documented migration path and release note.

Consumers should inspect `schema_version`, preserve unknown metric keys when relaying reports, and
use `completed_checks`, `unknown_checks`, and `coverage_percent` rather than inferring completeness
from score. History entries are ordinary schema-4 reports and use the same validated reader.
Comparison ignores process-attribution samples because process names and IDs are ephemeral evidence,
not stable trends.
