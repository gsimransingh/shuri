# Shuri roadmap

Shuri is a lightweight Windows workstation-readiness CLI. Its value is fast, explainable evidence
for a person sitting at one machine. The feature scope is now frozen: progress toward 1.0 means
making the existing tool safer, more reliable, and faster—not adding breadth.

## Product boundaries

Keep:

- Read-only checks with a clear support action.
- Transparent scoring and optional redacted JSON export.
- Windows-first validation and portable runtime behavior that does not claim Windows-native evidence
  elsewhere.

Avoid:

- Agents, telemetry, accounts, dashboards, remote control, or background monitoring.
- Local report history, comparison, report databases, multiple report formats, and automatic process
  attribution.
- Configuration systems and policy engines unless essential to a concrete readiness check.
- Platform expansion that cannot be maintained and tested.

## Path to 1.0

### 1. Security confidence

- Review every external command, file write, JSON export, and dependency.
- Keep checks read-only and make failure modes explicit.
- Confirm that exports redact the identifiers they claim to redact.

### 2. Windows reliability

- Exercise ordinary Windows edge cases: restricted PowerShell, unavailable Defender, no battery,
  offline network, unusual storage, and slow Windows Update.
- Make unsupported or unavailable evidence `UNKNOWN`, never a guessed pass or failure.
- Preserve small, focused automated and real-Windows integration coverage.

### 3. Speed and simplicity

- Measure `shuri doctor` startup and total scan time on representative workstations.
- Set bounded timeouts for slow native facilities and remove work that does not change the result.
- Keep the `shuri` command surface small and the dependency set minimal.

### 4. Distribution decision

- Keep the latest release as-is; do not publish a new package or standalone executable during this
  phase.
- The current unsigned executable is not an end-user distribution channel because Windows trust and
  Defender classification must be resolved first.
- Decide deliberately later between Python/pipx installation for support users, signed enterprise
  deployment, or Store distribution. This is not a feature milestone.

### 5. 1.0 gate

Call Shuri 1.0 only when the existing Windows workflow is secure, reliable on the supported edge
cases, consistently fast, and has a deliberate installation story. No calendar date is attached.

After 1.0, keep the feature scope frozen. Maintenance fixes for security or Windows compatibility
remain possible when necessary.
