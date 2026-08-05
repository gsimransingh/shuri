# Platform support

Shuri 0.5.0 is developed primarily for Windows. Portable checks also run on Linux and macOS, but
support is stated per check so an unavailable native facility is never mistaken for a failure.

## Support levels

- **Supported:** intended product behavior and exercised by continuous integration.
- **Best effort:** implemented through portable libraries, but not fully covered on that platform.
- **Unavailable:** the check returns `UNKNOWN` without reducing the health score.

## Check matrix

| Check | Windows 10/11 | Ubuntu Linux | macOS | Notes |
| --- | --- | --- | --- | --- |
| System | Supported | Supported | Best effort | OS identity, uptime, memory, and system disk |
| CPU | Supported | Supported | Best effort | Utilisation and bounded attribution when elevated |
| Memory | Supported | Supported | Best effort | Pressure and bounded attribution when elevated |
| Disk | Supported | Supported | Best effort | Capacity for accessible mounted filesystems |
| Physical drives | Supported | Unavailable | Unavailable | Windows state; optional counters are device-dependent |
| Network | Supported | Supported, basic | Best effort, basic | Gateway and DNS inventory are Windows-only |
| Battery | Supported when present | Best effort | Best effort | Capacity health is Windows-only |
| Services | Supported | Unavailable | Unavailable | Selected Windows services only |
| Updates | Supported | Unavailable | Unavailable | Windows Update and pending restart only |
| Antivirus | Supported | Unavailable | Unavailable | Defender plus third-party product discovery |
| Event logs | Supported | Unavailable | Unavailable | Windows System log, newest 50 matching events |

The Ubuntu column reflects the current GitHub Actions runner, not every Linux distribution. macOS
remains best effort until it has dedicated CI and native integrations. Windows checks can be
`UNKNOWN` when policy, permissions, hardware, services, storage controllers, or vendor drivers
prevent collection. Missing drive counters are not interpreted as healthy evidence. See
[physical-drive health](physical-drive-health.md) and
[process-attribution privacy](process-attribution.md).

## Safe integration coverage

Unit tests mock platform-command boundaries. Windows CI additionally runs opt-in, read-only
PowerShell boundary checks, including physical-drive discovery. They never change services,
updates, registry data, security settings, storage state, or event logs.
