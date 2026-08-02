"""Typed, versioned health-assessment policy."""

from __future__ import annotations

from dataclasses import dataclass, fields

from shuri.version import SCORING_POLICY_VERSION


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    """Thresholds and deduction weights used by the standard assessment."""

    version: int = SCORING_POLICY_VERSION
    high_cpu_percent: float = 85.0
    critical_cpu_percent: float = 95.0
    low_memory_percent: float = 20.0
    critical_memory_percent: float = 10.0
    low_disk_percent: float = 15.0
    critical_disk_percent: float = 10.0
    high_swap_percent: float = 80.0
    low_battery_charge_percent: float = 10.0
    low_battery_health_percent: float = 80.0
    critical_battery_health_percent: float = 60.0
    stale_antivirus_signature_days: int = 14
    repeated_error_event_count: int = 5
    high_drive_temperature_celsius: float = 70.0
    high_drive_wear_percent: float = 90.0
    high_cpu_points: int = 5
    critical_cpu_points: int = 10
    low_memory_points: int = 5
    critical_memory_points: int = 10
    high_swap_points: int = 5
    low_system_disk_points: int = 8
    critical_system_disk_points: int = 15
    critical_other_disk_points: int = 5
    pending_restart_points: int = 5
    available_updates_points: int = 3
    low_battery_charge_points: int = 3
    low_battery_health_points: int = 3
    critical_battery_health_points: int = 5
    no_network_adapter_points: int = 10
    dns_failure_points: int = 5
    reachability_failure_points: int = 5
    stopped_service_points: int = 8
    antivirus_disabled_points: int = 20
    realtime_antivirus_disabled_points: int = 10
    stale_antivirus_signatures_points: int = 5
    critical_event_points: int = 10
    repeated_error_event_points: int = 5
    physical_drive_warning_points: int = 8
    physical_drive_failure_points: int = 20

    def __post_init__(self) -> None:
        point_fields = (
            getattr(self, item.name) for item in fields(self) if item.name.endswith("_points")
        )
        if any(value < 0 for value in point_fields):
            raise ValueError("Scoring-policy deduction points cannot be negative.")


DEFAULT_POLICY = ScoringPolicy()
