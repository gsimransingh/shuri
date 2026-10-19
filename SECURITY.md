# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/gsimransingh/shuri/security/advisories/new)
instead of opening a public issue. Include the Shuri version (`shuri version`), your Windows
version, and the steps to reproduce. Expect an acknowledgement within a week.

Only the latest release receives security fixes.

## Security model

Shuri is a local, read-only diagnostic tool. These guarantees are tested and are the baseline for
every change:

- **No shell, fixed programs.** Windows tools (`powershell.exe`, `sc.exe`, `powercfg.exe`) are run
  without a shell, by absolute path from the Windows System32 directory, with that directory as the
  working directory. A look-alike program in the current folder or on `PATH` is never launched, and
  a program outside that fixed list is refused.
- **Read-only.** Checks query state; they never change services, settings, files or the network.
  The one temporary file (the battery report) has a random name and is deleted afterwards.
- **No telemetry, no outbound traffic by default.** Shuri sends nothing anywhere. The default scan
  is fully local. Only `--probe` makes network calls: one DNS lookup and one TCP connection to the
  documented probe targets, with nothing sent over the connection (see the README).
- **Safe exports.** JSON reports are redacted by default using an allow-list, so an unreviewed
  field is hidden rather than leaked. Exports never overwrite an existing file without `--force`,
  never follow symbolic links, and are written atomically. `--raw` keeps identifiers and prints a
  warning.
- **Supply chain.** CI dependencies are hash-locked (`requirements/lock-py312.txt`), GitHub Actions
  are pinned to commit SHAs, and CodeQL, `pip-audit` and Ruff security rules run on every change.

## Out of scope

Shuri trusts the local Windows installation it inspects. A machine already controlled by an
attacker (for example one with a modified System32 directory) cannot be assessed reliably by any
user-mode tool.
