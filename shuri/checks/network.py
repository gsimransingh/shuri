"""Network inventory and basic reachability checks."""

from __future__ import annotations

import json
import socket
from typing import Any

import psutil

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.models.network import AdapterSnapshot
from shuri.utils.constants import CONNECTIVITY_HOST, CONNECTIVITY_PORT
from shuri.utils.platform import is_windows, run_powershell


def _can_resolve(hostname: str) -> bool:
    try:
        socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    return True


def _can_connect(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def _adapter_snapshots() -> tuple[AdapterSnapshot, ...]:
    """Collect interface state, IP addresses, and MAC addresses through psutil."""
    addresses = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    link_family = getattr(psutil, "AF_LINK", None)
    adapters: list[AdapterSnapshot] = []
    for name, values in addresses.items():
        ip_addresses = tuple(
            address.address
            for address in values
            if address.family in (socket.AF_INET, socket.AF_INET6)
        )
        mac_address = next(
            (
                address.address
                for address in values
                if link_family is not None and address.family == link_family
            ),
            None,
        )
        adapters.append(
            AdapterSnapshot(
                name=name,
                is_up=bool(stats.get(name) and stats[name].isup),
                addresses=ip_addresses,
                mac_address=mac_address,
            )
        )
    return tuple(adapters)


def parse_windows_network_configuration(payload: str) -> tuple[str | None, tuple[str, ...]]:
    """Extract the primary IPv4 gateway and configured DNS servers from PowerShell JSON."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None, ()
    entries = parsed if isinstance(parsed, list) else [parsed]
    gateways: list[str] = []
    dns_servers: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        gateways.extend(_string_values(entry.get("Gateway")))
        dns_servers.extend(_string_values(entry.get("DnsServers")))
    primary_gateway = gateways[0] if gateways else None
    return primary_gateway, tuple(dict.fromkeys(dns_servers))


def _string_values(value: Any) -> tuple[str, ...]:
    """Normalise PowerShell's scalar-or-array JSON properties into strings."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, str) and item)
    return ()


def _windows_network_configuration() -> tuple[str | None, tuple[str, ...]]:
    """Use Windows' networking API to obtain default gateway and DNS settings."""
    if not is_windows():
        return None, ()
    script = """
    Get-NetIPConfiguration | ForEach-Object {
        [PSCustomObject]@{
            Gateway = @($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop })
            DnsServers = @($_.DNSServer.ServerAddresses)
        }
    } | ConvertTo-Json -Depth 3 -Compress
    """
    output = run_powershell(script, timeout=5)
    return parse_windows_network_configuration(output) if output else (None, ())


def check_network() -> CheckResult:
    """Collect network identity, configuration, DNS health, and reachability."""
    adapters = _adapter_snapshots()
    active = tuple(adapter for adapter in adapters if adapter.is_up and adapter.addresses)
    default_gateway, dns_servers = _windows_network_configuration()
    dns_resolution = _can_resolve("example.com")
    connectivity = _can_connect(CONNECTIVITY_HOST, CONNECTIVITY_PORT)
    status = CheckStatus.PASS
    deductions: list[ScoreDeduction] = []
    findings: list[str] = []
    if not active:
        status = CheckStatus.FAIL
        findings.append("No active network adapter with an IP address was found.")
        deductions.append(ScoreDeduction("No active network adapter was found", 10, "network"))
    if not dns_resolution:
        status = CheckStatus.WARNING if status is CheckStatus.PASS else status
        findings.append("DNS resolution for example.com failed.")
        deductions.append(ScoreDeduction("DNS resolution failed", 5, "network"))
    if not connectivity:
        status = CheckStatus.WARNING if status is CheckStatus.PASS else status
        findings.append("A short internet reachability check failed.")
        deductions.append(ScoreDeduction("Internet reachability check failed", 5, "network"))
    dns_state = "available" if dns_resolution else "unavailable"
    return CheckResult(
        name="network",
        title="Network",
        status=status,
        summary=f"{len(active)} active adapter(s); DNS {dns_state}.",
        metrics={
            "hostname": socket.gethostname(),
            "default_gateway": default_gateway,
            "dns_servers": list(dns_servers),
            "dns_resolution": dns_resolution,
            "internet_connectivity": connectivity,
            "adapters": [
                {
                    "name": adapter.name,
                    "is_up": adapter.is_up,
                    "addresses": list(adapter.addresses),
                    "mac_address": adapter.mac_address,
                }
                for adapter in adapters
            ],
        },
        findings=tuple(findings),
        deductions=tuple(deductions),
    )
