"""Network inventory and basic reachability checks."""

from __future__ import annotations

import json
import os
import socket
from typing import Any

import psutil

from shuri.core.policy import DEFAULT_POLICY
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.models.network import AdapterSnapshot
from shuri.utils.constants import CONNECTIVITY_HOST, CONNECTIVITY_PORT, DNS_PROBE_HOST
from shuri.utils.platform import command_failure_message, is_windows, run_powershell


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


def _windows_network_configuration() -> tuple[str | None, tuple[str, ...], str | None]:
    """Use Windows' networking API to obtain default gateway and DNS settings."""
    if not is_windows():
        return None, (), None
    script = """
    Get-NetIPConfiguration | ForEach-Object {
        [PSCustomObject]@{
            Gateway = @($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop })
            DnsServers = @($_.DNSServer.ServerAddresses)
        }
    } | ConvertTo-Json -Depth 3 -Compress
    """
    result = run_powershell(script, timeout=5)
    if not result.succeeded:
        return None, (), command_failure_message("Windows network configuration", result)
    gateway, servers = parse_windows_network_configuration(result.output)
    return gateway, servers, None


def _probe_configuration() -> tuple[str, str, int]:
    """Read organization-specific probe targets from bounded environment settings."""
    dns_host = os.environ.get("SHURI_DNS_PROBE_HOST", DNS_PROBE_HOST).strip() or DNS_PROBE_HOST
    connect_host = (
        os.environ.get("SHURI_CONNECTIVITY_HOST", CONNECTIVITY_HOST).strip() or CONNECTIVITY_HOST
    )
    try:
        connect_port = int(os.environ.get("SHURI_CONNECTIVITY_PORT", CONNECTIVITY_PORT))
    except (TypeError, ValueError):
        connect_port = CONNECTIVITY_PORT
    if not 1 <= connect_port <= 65_535:
        connect_port = CONNECTIVITY_PORT
    return dns_host, connect_host, connect_port


def check_network() -> CheckResult:
    """Collect network identity, configuration, DNS health, and reachability."""
    adapters = _adapter_snapshots()
    active = tuple(adapter for adapter in adapters if adapter.is_up and adapter.addresses)
    default_gateway, dns_servers, configuration_error = _windows_network_configuration()
    dns_host, connect_host, connect_port = _probe_configuration()
    dns_resolution = _can_resolve(dns_host)
    connectivity = _can_connect(connect_host, connect_port)
    status = CheckStatus.PASS
    deductions: list[ScoreDeduction] = []
    findings: list[str] = []
    if not active:
        status = CheckStatus.FAIL
        findings.append("No active network adapter with an IP address was found.")
        deductions.append(
            ScoreDeduction(
                "No active network adapter was found",
                DEFAULT_POLICY.no_network_adapter_points,
                "network",
            )
        )
    if not dns_resolution:
        status = CheckStatus.WARNING if status is CheckStatus.PASS else status
        findings.append("The configured DNS probe failed; review the probe target in metrics.")
        deductions.append(
            ScoreDeduction("DNS resolution failed", DEFAULT_POLICY.dns_failure_points, "network")
        )
    if not connectivity:
        status = CheckStatus.WARNING if status is CheckStatus.PASS else status
        findings.append("The configured TCP probe failed; review the probe target in metrics.")
        deductions.append(
            ScoreDeduction(
                "Configured TCP connectivity probe failed",
                DEFAULT_POLICY.reachability_failure_points,
                "network",
            )
        )
    if configuration_error:
        findings.append(configuration_error)
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
            "dns_probe": {"target": dns_host, "succeeded": dns_resolution},
            "tcp_probe": {
                "target": connect_host,
                "port": connect_port,
                "succeeded": connectivity,
            },
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
