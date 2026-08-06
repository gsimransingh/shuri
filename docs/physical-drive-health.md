# Physical-drive health

Shuri 0.4.0 introduced read-only Windows physical-drive diagnostics. Shuri 0.5.3 adds native Linux
and macOS evidence. This complements filesystem capacity: a volume can have free space while its
underlying device reports an unhealthy state.

## Evidence collected

Shuri requests model, device identifier, media type, bus type, capacity, health state, and
operational state. Windows uses Storage Management, Linux uses `lsblk` plus optional `smartctl`, and
macOS uses `diskutil`. When exposed by the platform, device, controller, and driver, Windows also
provides temperature, wear, read/write errors, and power-on hours. Serial numbers are not requested.

No self-test, benchmark, firmware operation, repair, or write is performed.

## Status rules

- `FAIL` requires an explicit unhealthy or failing native state.
- `WARNING` covers an explicit warning state, temperature at least 70 °C, or wear at least 90%.
- `PASS` requires explicit healthy and operational evidence.
- `UNKNOWN` means the native source could not supply trustworthy health evidence.
- A healthy device with unavailable optional counters remains healthy, with omissions reported.
- Mixed known and ambiguous devices produce a visible, non-scoring warning.

Missing SMART-style counters are never treated as proof of health. Scoring-policy version 2 assigns
at most one drive deduction: 20 points for explicit failure or 8 for warning.

## Platform and hardware limits

Windows Storage Management is built in. Linux inventory uses built-in `lsblk`; health requires the
optional smartmontools package and sufficient device access. macOS uses built-in `diskutil` SMART
status. NVMe, SATA, USB bridges, RAID, virtual disks, and vendor drivers expose different evidence.
Those differences safely become unavailable or unknown rather than assumed healthy.
