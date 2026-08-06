# Physical-drive health

Shuri uses read-only Windows Storage Management evidence to complement filesystem free-space checks.
It collects model, device identifier, media and bus type, capacity, health and operational state, and
available temperature, wear, error, and power-on counters. It never requests serial numbers or runs
self-tests, repairs, benchmarks, firmware operations, or writes.

- `FAIL` requires explicit native unhealthy evidence.
- `WARNING` covers an explicit warning state, temperature at least 70 °C, or wear at least 90%.
- `PASS` requires explicit healthy and operational evidence.
- `UNKNOWN` means Windows could not provide trustworthy health information.

Storage controllers, RAID layers, USB bridges, virtual disks, and vendor drivers can hide evidence.
Missing counters are never treated as proof of health.
