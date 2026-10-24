# Platform support

Windows 10 and 11 are Shuri’s supported workstation platforms. Windows runs in continuous
integration, including safe read-only PowerShell and physical-drive checks.

| Check | Windows | Linux/macOS |
| --- | --- | --- |
| CPU, memory, disk, network, battery, system | Supported where hardware exposes evidence | Portable best effort |
| Physical drives | Supported through Windows Storage Management | Unavailable |
| Services, updates, Defender, event logs | Supported through Windows-native facilities | Unavailable |

A check that does not apply to the current platform returns `N/A` (Not Applicable): it does not
reduce the health score and is excluded from coverage, so a Linux or macOS scan reads as a complete
assessment of the checks that apply rather than an incomplete Windows scan. A check that *does*
apply but cannot get trustworthy evidence returns `UNKNOWN`, which lowers coverage. This lets Shuri
remain
runnable off Windows without pretending to provide an equivalent readiness assessment there.
