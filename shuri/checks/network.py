"""Network inventory and basic reachability checks."""

from __future__ import annotations

import socket

import psutil

from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.models.network import AdapterSnapshot
from shuri.utils.constants import CONNECTIVITY_HOST, CONNECTIVITY_PORT


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


def check_network() -> CheckResult:
    """Collect adapters, verify DNS, and make a short TCP reachability attempt."""
    addresses = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    adapters = tuple(
        AdapterSnapshot(
            name=name,
            is_up=bool(stats.get(name) and stats[name].isup),
            addresses=tuple(
                address.address
                for address in values
                if address.family in (socket.AF_INET, socket.AF_INET6)
            ),
        )
        for name, values in addresses.items()
    )
    active = tuple(adapter for adapter in adapters if adapter.is_up and adapter.addresses)
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
            "dns_resolution": dns_resolution,
            "internet_connectivity": connectivity,
            "adapters": [
                {"name": adapter.name, "is_up": adapter.is_up, "addresses": list(adapter.addresses)}
                for adapter in adapters
            ],
        },
        findings=tuple(findings),
        deductions=tuple(deductions),
    )
