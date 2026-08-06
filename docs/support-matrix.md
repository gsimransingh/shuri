# Platform support

Shuri 0.5.3 is tested on Windows, macOS, Ubuntu, Debian, Fedora, and Arch Linux. Support is stated
per check so an unavailable native facility is never mistaken for a failure.

## Support levels

- **Supported:** intended product behavior and exercised by continuous integration.
- **Best effort:** implemented through portable libraries, but not fully covered on that platform.
- **Unavailable:** the check returns `UNKNOWN` without reducing the health score.

## Check matrix

| Check | Windows 10/11 | Ubuntu Linux | macOS | Notes |
| --- | --- | --- | --- | --- |
| System | Supported | Supported | Supported | OS identity, uptime, memory, and system disk |
| CPU | Supported | Supported | Supported | Utilisation and bounded attribution when elevated |
| Memory | Supported | Supported | Supported | Pressure and bounded attribution when elevated |
| Disk | Supported | Supported | Supported | Capacity for accessible mounted filesystems |
| Physical drives | Supported | Supported when exposed | Supported when exposed | Native inventory; SMART evidence varies by device, driver, tool, and access |
| Network | Supported | Supported, basic | Supported, basic | Gateway and DNS inventory are Windows-only |
| Battery | Supported when present | Supported when exposed | Supported when exposed | Capacity health is Windows-only |
| Services | Supported | Supported on systemd | Supported | Windows SCM, systemd, or launchd |
| Updates | Supported | Supported for apt/dnf/pacman | Supported | Windows Update, native package manager, or Software Update |
| Security posture | Supported | Supported when controls are exposed | Supported | Defender or native firewall/platform protections |
| System logs | Supported | Supported on systemd | Supported | Bounded metadata from Windows Event Log, journald, or unified logging |

Linux distribution adapters are exercised in Ubuntu, Debian, Fedora, and Arch containers; systemd
host behavior is additionally exercised on the Ubuntu runner. The macOS column reflects the current
GitHub-hosted macOS runner. Native checks can be `UNKNOWN` when
policy, permissions, hardware, services, tools, storage controllers, or vendor drivers
prevent collection. Missing drive counters are not interpreted as healthy evidence. See
[physical-drive health](physical-drive-health.md) and
[process-attribution privacy](process-attribution.md).

## Safe integration coverage

Every supported operating system runs the complete verification workflow, builds a wheel, tests an
installed command in a clean environment, and builds and smoke-tests its native standalone
executable. CI also runs opt-in, read-only native collector integration checks. Windows exercises
PowerShell boundaries and physical-drive discovery; Linux and macOS execute their native adapters.
They never change services, updates, registry data, security settings, storage state, or logs.
