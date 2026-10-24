# Shuri roadmap

Shuri answers one question for a person at a machine: **is this workstation ready to work?** It does
it with fast, read-only, explainable checks and a transparent score — no agent, account, telemetry
or background service.

Through 0.6.0 that promise was delivered for Windows. The direction from here is to make it true on
**Linux and macOS as well**, in two deliberate stages, without weakening the properties that make
the Windows tool trustworthy.

## Product boundaries (unchanged)

Keep:

- Read-only checks, each with a clear support action.
- Transparent scoring and optional redacted JSON export.
- Honest evidence: a check reports a real state or says it could not, and never guesses.

Avoid:

- Agents, telemetry, accounts, dashboards, remote control, or background monitoring.
- Local report history, comparison databases, or multiple report formats.
- Configuration systems and policy engines beyond what a concrete readiness check needs.
- **Untested platform code.** A native check for an OS ships only with CI that exercises it on that
  OS. This is the condition that lets cross-platform support exist without reintroducing guessed
  results.

## Where 0.6.0 landed

- **Security baseline:** system-directory-only process launch, allow-list redaction, safe atomic
  exports, hash-locked dependencies, `pip-audit`, CodeQL, SHA-pinned Actions.
- **Reliability:** per-check and per-scan deadlines, exit codes (0/1/2/3), honest "Incomplete"
  scores, error-class capture with `--debug`, `psutil`-based service checks.
- **CLI:** `shuri` runs the full check, `shuri check <name>` runs one, `--details` / `--json`,
  network probes behind an opt-in `--probe`.

Already cross-platform today: the scan auto-detects the OS and runs the portable checks (system,
CPU, memory, disk, network adapters, battery charge) everywhere, printing live results and an
optional report on any OS. The Windows-native checks (services, Windows Update, Defender, event
logs, physical-drive health) report `UNKNOWN` elsewhere, which makes a Linux or macOS result read as
"Incomplete". Native Linux/macOS equivalents existed in 0.5.3 (`native_unix.py`) and were removed in
0.5.4; they can be recovered from git history.

## Direction: cross-platform readiness, in two stages

### Stage 1 — An honest cross-platform baseline

Make a scan on Linux or macOS present a clean, truthful result instead of a scary "Incomplete",
without adding any new native collection yet.

- Distinguish **Not Applicable** (a Windows-only check running on Linux) from **Unknown** (a check
  that should work here but could not get evidence). Only genuine Unknowns should make a score
  incomplete; "not applicable on this OS" should not read as a failure to determine.
- Compute and present the score over the checks that *apply* to the current OS, and say plainly in
  the header which platform was assessed and which checks do not apply here.
- Keep the report (`--json`) coherent on every OS, with the platform and per-check applicability
  recorded.
- No scope reversal: this is presentation and scoring honesty, testable with the existing suite.

### Stage 2 — Restore native parity, tested

Bring back real Linux and macOS evidence so the result is as meaningful there as on Windows.

- Recover the 0.5.3 native collectors as a starting point: Linux physical drives via `lsblk` and
  SMART via `smartctl`; macOS via `diskutil`; Linux security posture (firewall, AppArmor/SELinux);
  macOS security posture (Gatekeeper, SIP, FileVault, application firewall).
- Map each to a readiness question a support person can act on; where an OS has no analog (there is
  no single "Windows Update" or "Defender"), leave it Not Applicable rather than inventing one.
- **Gate every native check behind CI that runs it on that OS** (GitHub Actions provides Linux and
  macOS runners). Keep the narrow, safe, read-only command discipline the Windows checks use.
- Apply the same safety baseline cross-platform: fixed executables resolved from trusted system
  paths, no shell, bounded timeouts, redaction of any new identifiers.

## Live tracks alongside the stages

These are not blocked by the cross-platform work and can proceed in parallel.

- **Speed.** Measure `shuri` startup and scan time, then bound the slow native facilities. The
  Windows Update check is roughly 15s of a ~16.5s scan; decide between a hard timeout, caching, or
  making it opt-in like the network probe.
- **Real-machine confidence.** Exercise ordinary edge cases on real hardware per OS: restricted
  PowerShell, unavailable Defender, no battery, offline network, unusual storage, standard vs admin.
  Confirm each becomes Unknown or Not Applicable, never a guessed pass or fail.

## Decisions still open

- **Is connectivity part of readiness?** Probing is opt-in today for the no-telemetry promise; a
  "ready to work" tool arguably should check reachability. Settle what the default scan means.
- **Distribution.** pipx-from-tag versus a signed executable, which gates non-technical users. The
  README install line references a `v0.6.0` tag that still needs to be created and pushed.
- **Is 1.0 the goal?** With scope frozen, "1.0" is a confidence statement, not a feature milestone.

## 1.0 gate

Call Shuri 1.0 when each supported platform's workflow is secure, reliable on its ordinary edge
cases, consistently fast, honest about what it did and did not assess, and has a deliberate
installation story. No calendar date is attached.
