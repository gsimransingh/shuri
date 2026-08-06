# Shuri scope

Shuri is a lightweight Windows workstation-readiness CLI. Its value is fast, explainable evidence
for a person sitting at one machine.

## Keep

- Read-only checks with a clear support action.
- Transparent scoring and optional redacted JSON export.
- A small Windows-first CI and standalone build.
- Portable runtime behavior that does not claim Windows-native evidence elsewhere.

## Avoid

- Agents, telemetry, accounts, dashboards, remote control, or background monitoring.
- Local report history, comparison, report databases, and multiple report formats.
- Configuration systems and policy engines unless they become essential to a concrete readiness check.
- Platform-specific expansion that cannot be maintained and tested.

The next work should improve reliability or clarity of an existing Windows check, not add breadth.
