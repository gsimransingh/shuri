# Report schema compatibility

Shuri application versions, report-schema versions, and scoring-policy versions are independent.
The current values in Shuri 0.3.0 are:

| Contract | Version | Purpose |
| --- | ---: | --- |
| Application | 0.3.0 | CLI and package release |
| Report schema | 2 | Stored and exported report structure |
| Scoring policy | 1 | Thresholds and deduction weights |

## Reader compatibility

Shuri 0.3.0 reads report schemas 0, 1, and 2:

- **Schema 0:** legacy reports without an explicit `schema_version`.
- **Schema 1:** trustworthy-assessment reports with coverage and policy metadata.
- **Schema 2:** adds the explicit top-level `redacted` state.

Older supported reports are normalized in memory to schema 2. When a legacy latest report is found
in the former workspace-local location, Shuri validates it and writes the normalized copy to the
current per-user location. The original file is not deleted.

Reports with an unknown future schema are rejected with an actionable message instead of being
partially interpreted. Corrupt JSON, invalid enum values, missing required fields, and invalid
field types are also rejected. Saved reports larger than 10 MiB are rejected before JSON parsing
to bound local memory use. Shuri writes only the current schema.

## Compatibility policy

- Adding an optional field requires a schema-version increment when its meaning affects consumers.
- Renaming, removing, or changing the meaning or type of a field requires a schema-version
  increment and an explicit migration or rejection path.
- Scoring changes increment `policy_version` independently of report structure.
- Application releases do not automatically increment either contract version.
- Support for old schemas may be removed only after a documented migration path and release note.

Consumers should inspect `schema_version` before relying on fields and should preserve unknown
metric keys when relaying reports. They must not infer assessment completeness from score alone;
use `completed_checks`, `unknown_checks`, and `coverage_percent`.

Report history does not introduce a new schema. Each retained entry is an ordinary schema-2 report,
and comparison reuses the validated report reader rather than defining a separate persisted format.
