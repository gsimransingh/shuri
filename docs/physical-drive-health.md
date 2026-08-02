# Physical-drive health

Shuri 0.4.0 adds a read-only Windows physical-drive diagnostic. It complements filesystem capacity:
a volume can have free space while its underlying device reports an unhealthy state.

## Evidence collected

Shuri requests model, device identifier, media type, bus type, capacity, Windows health state, and
operational state. When exposed by the device, controller, and driver, it also requests temperature,
wear, read/write errors, and power-on hours. Serial numbers are not requested.

No self-test, benchmark, firmware operation, repair, or write is performed.

## Status rules

- `FAIL` requires an explicit unhealthy or failing Windows state.
- `WARNING` covers an explicit warning state, temperature at least 70 °C, or wear at least 90%.
- `PASS` requires explicit healthy and operational evidence.
- `UNKNOWN` means Windows could not supply trustworthy health evidence.
- A healthy device with unavailable optional counters remains healthy, with omissions reported.
- Mixed known and ambiguous devices produce a visible, non-scoring warning.

Missing SMART-style counters are never treated as proof of health. Scoring-policy version 2 assigns
at most one drive deduction: 20 points for explicit failure or 8 for warning.

## Platform and hardware limits

Windows Storage Management is the supported source. NVMe often exposes core state but can omit
optional counters. SATA, USB bridges, RAID, virtual disks, and vendor drivers may hide or translate
reliability data. Those differences safely become unavailable or unknown evidence. Linux
`smartctl` is outside 0.4.0 because its package, privilege, and device-access contract is undefined.
