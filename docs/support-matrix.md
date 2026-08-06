# Platform support

Windows 10 and 11 are Shuri’s supported workstation platforms. Windows runs in continuous
integration, including safe read-only PowerShell and physical-drive checks.

| Check | Windows | Linux/macOS |
| --- | --- | --- |
| CPU, memory, disk, network, battery, system | Supported where hardware exposes evidence | Portable best effort |
| Physical drives | Supported through Windows Storage Management | Unavailable |
| Services, updates, Defender, event logs | Supported through Windows-native facilities | Unavailable |

An unavailable check returns `UNKNOWN` and does not reduce the health score. This lets Shuri remain
runnable off Windows without pretending to provide an equivalent readiness assessment there.
