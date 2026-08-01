# Platform support

Shuri 0.2.3 is developed primarily for Windows. Portable checks also run on Linux and macOS, but
support is stated per check so an unavailable native facility is never mistaken for a failure.

## Support levels

- **Supported:** intended product behavior and exercised by continuous integration.
- **Best effort:** implemented through portable libraries, but not fully covered on that platform.
- **Unavailable:** the check returns `UNKNOWN` without reducing the health score.

## Check matrix

| Check | Windows 10/11 | Ubuntu Linux | macOS | Notes |
| --- | --- | --- | --- | --- |
| System | Supported | Supported | Best effort | OS identity, uptime, memory, and system disk |
| CPU | Supported | Supported | Best effort | Utilisation, topology, frequency, and load when exposed |
| Memory | Supported | Supported | Best effort | Physical memory and swap through `psutil` |
| Disk | Supported | Supported | Best effort | Capacity for accessible mounted filesystems |
| Network | Supported | Supported, basic | Best effort, basic | Gateway and configured DNS inventory are currently Windows-only |
| Battery | Supported when present | Best effort | Best effort | Charge is portable; capacity health is currently Windows-only |
| Services | Supported | Unavailable | Unavailable | Selected Windows services only |
| Updates | Supported | Unavailable | Unavailable | Windows Update and pending-restart state only |
| Antivirus | Supported | Unavailable | Unavailable | Defender plus registered third-party product discovery |
| Event logs | Supported | Unavailable | Unavailable | Windows System log, newest 50 matching events |

The Ubuntu column reflects the current GitHub Actions runner, not every Linux distribution. macOS
remains best effort until it has dedicated CI and native integrations. Some Windows checks can be
`UNKNOWN` when local policy, permissions, hardware, or disabled services prevent collection.

## Safe integration coverage

Unit tests mock platform-command boundaries. Windows CI additionally runs an opt-in, read-only
PowerShell boundary check. It never changes services, updates, registry data, security settings, or
event logs.
