# Shuri roadmap

Updated: 2026-08-05 (Shuri 0.5.0, unreleased)

## Product direction

Shuri is a transparent, privacy-conscious workstation health assessment tool for IT support,
systems, and security teams. It combines scattered system signals into an explainable report
without requiring an agent, account, cloud service, or telemetry backend. It should remain
explainable, honest about uncertainty, local-first, read-only, bounded, and useful in first response.

## Current baseline — 0.5.0

- Eleven diagnostics cover CPU, memory, filesystems, physical drives, network, battery, system,
  Windows services, Windows Update, antivirus, and event logs.
- Elevated CPU and memory results include bounded, privacy-governed process attribution without
  changing healthy results or scoring.
- Physical-drive assessment separates explicit Windows failure evidence from missing counters.
- CPU is sampled before a bounded four-worker scan; reports record true wall-clock duration.
- Scoring is transparent, coverage-aware, and independently policy-versioned.
- Terminal, JSON, Markdown, and HTML reporters share one typed model and explicit redaction.
- Latest-report and 50-entry history storage are atomic, validated, and compatible with schemas 0–4.
- The Python 3.12 dependency graph is constrained and Dependabot monitors dependency updates.
- CI verifies Windows and Ubuntu, wheel installation, installed commands, and a smoke-tested
  single-file Windows executable.

## Completed milestones

| Milestone | Release | Outcome |
| --- | --- | --- |
| Trustworthy assessments | 0.2.1 | Coverage, validation, versioned policy |
| Reliable daily use | 0.2.2 | Atomic storage, progress, privacy, Windows probes |
| Test and release confidence | 0.2.3–0.2.4 | Cross-platform CI, packaging and integration |
| Local history and comparison | 0.3.0 | Retention, cleanup, status changes, metric trends |
| Storage and delivery reliability | 0.4.0 | Drive health, concurrency, pinned inputs, executable |
| Privacy-bounded resource attribution | 0.5.0 | Top contributors, redaction, bounded collection |

## Current limitations

- The executable is unsigned, so Windows reputation controls may warn or block it.
- Windows Update is usually the longest diagnostic and can dominate total duration.
- Drive counters vary across NVMe, SATA, USB, RAID, virtual storage, and vendor drivers; unavailable
  evidence remains `UNKNOWN`.
- Linux covers portable checks only; macOS remains best effort without dedicated CI.
- Service expectations and scoring thresholds are not user-configurable.
- Shuri has no GUI, fleet dashboard, remote management, or background monitoring.

## Next milestone — organization policy (planned for 0.6.0)

- Configurable service sets and network targets.
- Named, validated scoring profiles with explicit policy versions.
- Validated policy import/export without silent changes.

### Delivery and platform backlog

- Code-sign release executables and define trustworthy update delivery.
- Add macOS CI before promoting macOS behavior to supported.
- Evaluate Linux drive health after defining dependency and privilege requirements.
- Continue profiling Windows Update without weakening evidence or timeout boundaries.

## Immediate next steps

1. Define a validated organization-policy document and compatibility rules.
2. Make service sets and network targets configurable without unsafe defaults.
3. Specify named scoring-profile validation and explicit policy-version behavior.
4. Add policy import/export fixtures before connecting configuration to live checks.
