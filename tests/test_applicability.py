"""Stage 1: a check that does not apply to this machine is Not Applicable, not Unknown.

These are the honesty guarantees that let a Linux or macOS scan read truthfully instead of looking
like a broken, incomplete Windows scan. Not Applicable never lowers coverage or the score, while a
genuine Unknown (a check that should work here but could not get evidence) still does.
"""

from __future__ import annotations

import re

import pytest
from rich.console import Console

from shuri.checks import antivirus, battery, eventlogs, physical_drives, services, updates
from shuri.core import assess_health
from shuri.core.exitcodes import ExitCode, exit_code_for
from shuri.models import CheckResult, CheckStatus, Report
from shuri.reporters.terminal import show_report

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

_WINDOWS_ONLY = (
    (antivirus, antivirus.check_antivirus),
    (eventlogs, eventlogs.check_event_logs),
    (physical_drives, physical_drives.check_physical_drives),
    (services, services.check_services),
    (updates, updates.check_updates),
)


@pytest.mark.parametrize("module, check", _WINDOWS_ONLY)
def test_windows_only_checks_are_not_applicable_off_windows(
    monkeypatch: pytest.MonkeyPatch, module: object, check: object
) -> None:
    monkeypatch.setattr(module, "is_windows", lambda: False)

    result = check()  # type: ignore[operator]

    assert result.status is CheckStatus.NOT_APPLICABLE
    assert "not applicable" in result.summary.casefold()
    assert result.deductions == ()


def test_absent_battery_is_not_applicable_not_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(battery.psutil, "sensors_battery", lambda: None)

    result = battery.check_battery()

    assert result.status is CheckStatus.NOT_APPLICABLE
    assert result.deductions == ()


def _results(*statuses: CheckStatus) -> tuple[CheckResult, ...]:
    return tuple(CheckResult(f"c{i}", f"C{i}", status, "s") for i, status in enumerate(statuses))


def test_not_applicable_checks_are_excluded_from_coverage() -> None:
    results = _results(
        CheckStatus.PASS,
        CheckStatus.PASS,
        CheckStatus.NOT_APPLICABLE,
        CheckStatus.NOT_APPLICABLE,
    )

    assessment = assess_health(results)

    assert assessment.not_applicable_checks == ("c2", "c3")
    assert assessment.completed_checks == 2
    assert assessment.coverage_percent == 100.0  # 2 of 2 applicable, not 2 of 4
    assert assessment.label != "Incomplete"


def test_not_applicable_does_not_make_a_scan_incomplete() -> None:
    results = _results(CheckStatus.PASS, CheckStatus.WARNING, CheckStatus.NOT_APPLICABLE)

    assessment = assess_health(results)

    assert assessment.unknown_checks == ()
    # A real score label, not "Incomplete" (no deductions on these synthetic results -> 100).
    assert assessment.label == "Excellent"


def test_a_genuine_unknown_still_makes_a_scan_incomplete() -> None:
    results = _results(CheckStatus.PASS, CheckStatus.UNKNOWN, CheckStatus.NOT_APPLICABLE)

    assessment = assess_health(results)

    assert assessment.unknown_checks == ("c1",)
    assert assessment.label == "Incomplete"
    assert assessment.coverage_percent == 50.0  # 1 completed of 2 applicable


def test_all_not_applicable_is_incomplete_without_dividing_by_zero() -> None:
    assessment = assess_health(_results(CheckStatus.NOT_APPLICABLE, CheckStatus.NOT_APPLICABLE))

    assert assessment.coverage_percent == 0.0
    assert assessment.label == "Incomplete"


@pytest.mark.parametrize(
    ("statuses", "expected"),
    (
        ((CheckStatus.PASS, CheckStatus.NOT_APPLICABLE), ExitCode.OK),
        ((CheckStatus.WARNING, CheckStatus.NOT_APPLICABLE), ExitCode.WARNING),
        ((CheckStatus.NOT_APPLICABLE, CheckStatus.UNKNOWN), ExitCode.INCOMPLETE),
        ((CheckStatus.NOT_APPLICABLE, CheckStatus.FAIL), ExitCode.FAILED),
    ),
)
def test_not_applicable_is_ignored_by_exit_codes(
    statuses: tuple[CheckStatus, ...], expected: ExitCode
) -> None:
    assert exit_code_for(_results(*statuses)) is expected


def test_a_simulated_non_windows_scan_reads_honestly_not_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end: force the Windows-only checks off, and the scan should still give a real
    score with the five Windows checks marked Not Applicable rather than an Incomplete result."""
    from shuri.core import DiagnosticRunner, default_registry

    for module in (antivirus, eventlogs, physical_drives, services, updates):
        monkeypatch.setattr(module, "is_windows", lambda: False)

    results = DiagnosticRunner(default_registry()).run()
    assessment = assess_health(results)

    not_applicable = {r.name for r in results if r.status is CheckStatus.NOT_APPLICABLE}
    assert {"antivirus", "eventlogs", "physical_drives", "services", "updates"} <= not_applicable
    assert assessment.label != "Incomplete"
    assert exit_code_for(results) is not ExitCode.INCOMPLETE


def test_report_header_shows_platform_and_not_applicable_count() -> None:
    results = (
        CheckResult("system", "System", CheckStatus.PASS, "ok", metrics={"system": "Linux"}),
        CheckResult("cpu", "CPU", CheckStatus.PASS, "ok"),
        CheckResult("services", "Windows Services", CheckStatus.NOT_APPLICABLE, "n/a here"),
    )
    report = Report.create(results, "host", assess_health(results))

    buffer = Console(record=True, width=100)
    show_report(report, console=buffer)
    text = _ANSI.sub("", buffer.export_text())

    assert "Not applicable on Linux: 1 check(s)" in text
    assert "N/A" in text
    assert "/2 applicable checks" in text  # coverage denominator excludes the N/A check
    assert "Incomplete" not in text
