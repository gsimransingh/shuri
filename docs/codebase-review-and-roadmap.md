# Shuri roadmap

Updated: 2026-08-02 (Shuri 0.3.0)

## Product direction

Shuri is a transparent, privacy-conscious workstation health assessment tool for IT support,
systems, and security teams. It combines scattered system signals into an explainable report
without requiring a monitoring agent, user account, cloud service, or telemetry backend.

Shuri should remain:

- **Explainable:** every health deduction identifies its reason and source check.
- **Honest about uncertainty:** unavailable evidence is `UNKNOWN`, never silently healthy.
- **Local-first:** complete reports and history remain on the workstation unless explicitly shared.
- **Safe:** diagnostics are read-only, bounded, and independently fault-tolerant.
- **Useful in first response:** results should help a technician decide what to investigate next.

## Current baseline — 0.3.0

Shuri currently provides:

- CPU, memory, filesystem capacity, network, battery, system, Windows service, Windows Update,
  Microsoft Defender, and Windows event-log diagnostics.
- Transparent health scoring with explicit deductions, assessment coverage, and policy versioning.
- Terminal, JSON, Markdown, and HTML reporting from one typed report model.
- Explicit share-safe redaction while preserving complete local evidence.
- Atomic per-user latest-report storage with legacy migration and defensive schema validation.
- Local retention of the newest 50 assessed reports.
- Assessment comparison across score, coverage, diagnostic statuses, and selected metric trends.
- Windows and Ubuntu CI, strict typing, linting, formatting, unit tests, a safe Windows integration
  check, clean wheel installation, and installed-command smoke tests.

## Completed milestones

| Milestone | Release | Outcome |
| --- | --- | --- |
| Trustworthy assessments | 0.2.1 | Coverage-aware scoring, schema validation, versioned policy, safe report loading |
| Reliable daily use | 0.2.2 | Stable atomic storage, progress, failure categories, privacy controls, better Windows probes |
| Test and release confidence | 0.2.3–0.2.4 | Cross-platform CI, packaging verification, Windows integration coverage, Defender date fix |
| Local history and comparison | 0.3.0 | Retained assessments, cleanup controls, status changes, and metric trends |

## Current limitations

- Installation requires Python 3.12 and is less convenient than a signed standalone executable.
- A complete Windows assessment usually takes 17–21 seconds; Windows Update and network queries
  dominate the duration.
- Linux support covers portable checks only, and macOS remains best effort without dedicated CI.
- Filesystem capacity is reported, but physical-drive health and SMART/reliability evidence are not.
- High CPU or memory usage is detected without identifying the responsible processes.
- Service expectations and scoring thresholds are not yet user-configurable.
- Shuri has no GUI, fleet dashboard, remote management, or background monitoring.
- Development and release dependency resolution is not pinned by a constraints or lock strategy.

## Milestone 5 — physical storage reliability (planned for 0.4.0)

The next release will distinguish a filesystem that merely has enough free space from a physical
drive that may be degrading. The implementation remains read-only and treats unavailable vendor or
platform data as unknown rather than healthy or failed.

### Scope

- Add a physical-drive diagnostic on supported Windows systems using native storage facilities.
- Report model, media type, bus type, operational status, and Windows health status when available.
- Collect bounded reliability counters such as temperature, wear, and read/write error indicators
  only when Windows and the device expose them reliably.
- Separate explicit failure evidence from unsupported hardware, missing counters, permissions, and
  vendor-specific omissions.
- Add conservative, transparent deductions only for trustworthy unhealthy states. Any scoring
  change must increment the scoring-policy version independently of the report schema.
- Include physical-drive results in terminal, JSON, Markdown, and HTML reports and in redaction
  review.
- Add mocked status-branch tests plus a safe, opt-in Windows integration boundary test.
- Document support differences for NVMe, SATA SSD, HDD, USB, virtual, and RAID-managed storage.

### Out of scope

- Destructive self-tests, firmware changes, repair commands, or write benchmarks.
- Vendor-specific tools or kernel drivers.
- Predicting an exact remaining drive lifetime.
- Linux `smartctl` integration until its dependency and privilege model are explicitly designed.

### Exit criteria

- Shuri never labels unavailable SMART/reliability evidence as a healthy drive.
- A known unhealthy Windows physical drive produces an actionable result with evidence and a
  transparent deduction.
- Unsupported and virtual storage degrade safely to `UNKNOWN` without reducing assessment score.
- All output formats agree on the physical-drive result and redact any newly identified sensitive
  fields.
- The complete verifier passes locally and in the Windows/Ubuntu CI matrix, including wheel smoke
  tests and the safe Windows integration boundary.

## Later candidates

### 0.5.0 — actionable resource attribution

- Identify bounded top CPU and memory consumers when a resource check is elevated.
- Collect process names and resource values, never command lines or process environment data.
- Define redaction and sharing behavior before enabling process evidence in exports.

### 0.6.0 — organization policy

- Configurable required-service sets and network probe targets.
- Named, validated scoring profiles with explicit policy versions.
- Import/export of policy files without remote management or silent configuration changes.

### Delivery and performance backlog

- Measure per-check latency and consider bounded concurrency only when results remain deterministic.
- Add macOS CI before promoting any macOS check from best effort to supported.
- Evaluate a tested dependency-constraints strategy for reproducible development and releases.
- Evaluate signed standalone Windows distribution after CLI behavior and update delivery are stable.

## Immediate next steps

1. Define the physical-drive result contract and exact `PASS`/`WARNING`/`FAIL`/`UNKNOWN` rules.
2. Capture representative read-only Windows storage payloads for NVMe, SATA, USB, virtual, and
   RAID-managed devices without committing machine identifiers.
3. Build pure parsing and assessment functions around those fixtures before wiring native commands.
4. Decide whether trustworthy failure states require scoring-policy version 2.
