from __future__ import annotations

from rich.console import Console

from shuri.core.scoring import assess_health
from shuri.models import CheckResult, CheckStatus, Report, ScoreDeduction
from shuri.reporters import render_html, render_json, render_markdown
from shuri.reporters.terminal import show_check, show_check_details


def _report() -> Report:
    return Report.create(
        hostname="workstation-01",
        results=(
            CheckResult(
                name="cpu",
                title="CPU",
                status=CheckStatus.PASS,
                summary="CPU utilisation is normal.",
                metrics={"utilisation_percent": 12.5},
            ),
        ),
    )


def test_json_report_is_machine_readable() -> None:
    rendered = render_json(_report())

    assert '"hostname": "workstation-01"' in rendered
    assert '"status": "pass"' in rendered


def test_human_reporters_include_the_check_summary() -> None:
    report = _report()

    assert "CPU utilisation is normal." in render_markdown(report)
    assert "CPU utilisation is normal." in render_html(report)


def test_reports_include_the_explicit_score_calculation() -> None:
    result = CheckResult(
        name="disk",
        title="Disk",
        status=CheckStatus.WARNING,
        summary="Disk is low.",
        deductions=(ScoreDeduction("System drive is below 15% free", 8, "disk"),),
    )
    report = Report.create(
        hostname="workstation-01",
        results=(result,),
        assessment=assess_health((result,)),
    )

    assert '"total_deductions": 8' in render_json(report)
    assert "100 - 8 deduction point(s) = 92" in render_markdown(report)
    assert "100 - 8 deduction point(s)" in render_html(report)


def test_reports_expose_incomplete_assessment_coverage() -> None:
    result = CheckResult("updates", "Updates", CheckStatus.UNKNOWN, "Unavailable")
    report = Report.create((result,), "workstation-01", assess_health((result,)))

    rendered_json = render_json(report)
    assert '"label": "Incomplete"' in rendered_json
    assert '"coverage_percent": 0.0' in rendered_json
    assert "0/1 checks completed" in render_markdown(report)
    assert "0/1" in render_html(report)


def test_reporters_escape_collected_text() -> None:
    result = CheckResult(
        name="unsafe",
        title="Unsafe | check",
        status=CheckStatus.WARNING,
        summary="<script>alert(1)</script> | next\nrow",
        metrics={"unsafe_value": "<img src=x> | value"},
        findings=("[click](javascript:alert(1))",),
    )
    report = Report.create((result,), "<host>")

    markdown = render_markdown(report)
    html = render_html(report)

    assert "<script>" not in markdown
    assert "Unsafe \\| check" in markdown
    assert "next row" in markdown
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_terminal_summarises_structured_metrics_without_dumping_json() -> None:
    result = CheckResult(
        name="network",
        title="Network",
        status=CheckStatus.PASS,
        summary="Network is available.",
        metrics={
            "dns_servers": ["192.168.1.1", "fe80::1", "fe80::2", "fe80::3"],
            "dns_probe": {"target": "example.com", "succeeded": True},
            "adapters": [
                {"name": "Wi-Fi", "is_up": True, "addresses": ["192.168.1.2"]},
                {"name": "Ethernet", "is_up": False, "addresses": []},
            ],
        },
    )
    console = Console(record=True, width=120, color_system=None)

    show_check(result, console)

    rendered = console.export_text()
    assert "Working" in rendered
    assert "1 active of 2 detected" in rendered
    assert "4 configured" in rendered
    assert '"target"' not in rendered
    assert '"addresses"' not in rendered


def test_terminal_summarises_physical_drive_inventory() -> None:
    result = CheckResult(
        name="physical_drives",
        title="Physical Drives",
        status=CheckStatus.PASS,
        summary="Drive health is available.",
        metrics={
            "physical_drives": [
                {"model": "Example SSD", "health_status": "Healthy", "size_bytes": 1_000}
            ]
        },
    )
    console = Console(record=True, width=100, color_system=None)

    show_check(result, console)

    rendered = console.export_text()
    assert "1 healthy of 1 detected" in rendered
    assert '"model"' not in rendered


def test_terminal_details_render_adapter_rows() -> None:
    result = CheckResult(
        name="network",
        title="Network",
        status=CheckStatus.PASS,
        summary="Healthy.",
        metrics={"adapters": [{"name": "Wi-Fi", "is_up": True, "addresses": ["192.168.1.2"]}]},
    )
    console = Console(record=True, width=120, color_system=None)

    show_check_details(result, console)

    rendered = console.export_text()
    assert "Network Adapters" in rendered
    assert "Wi-Fi" in rendered
    assert "Connected" in rendered
    assert "192.168.1.2" in rendered


def test_terminal_summarises_services_and_defender_plainly() -> None:
    result = CheckResult(
        name="security",
        title="Security",
        status=CheckStatus.PASS,
        summary="Healthy.",
        metrics={
            "services": {
                "one": {"state": "running"},
                "two": {"state": "stopped"},
            },
            "defender": {
                "AMServiceEnabled": True,
                "AntivirusEnabled": True,
                "RealTimeProtectionEnabled": True,
            },
        },
    )
    console = Console(record=True, width=120, color_system=None)

    show_check(result, console)

    rendered = console.export_text()
    assert "1 running of 2 monitored" in rendered
    assert "Enabled; real-time protection on" in rendered
    assert "detail(s) available" not in rendered


def test_terminal_details_render_native_security_controls() -> None:
    result = CheckResult(
        name="antivirus",
        title="Security Posture",
        status=CheckStatus.PASS,
        summary="Healthy.",
        metrics={
            "security_controls": {
                "gatekeeper": ["enabled", "assessments enabled"],
                "firewall": ["disabled", "state = 0"],
            }
        },
    )
    console = Console(record=True, width=120, color_system=None)

    show_check_details(result, console)

    rendered = console.export_text()
    assert "Native Security Controls" in rendered
    assert "Gatekeeper" in rendered
    assert "Enabled" in rendered


def _attributed_report() -> Report:
    return Report.create(
        (
            CheckResult(
                "cpu",
                "CPU",
                CheckStatus.WARNING,
                "CPU utilisation is elevated.",
                metrics={
                    "process_attribution": {
                        "resource": "cpu",
                        "state": "complete",
                        "contributors": [
                            {
                                "process_name": "worker.exe",
                                "process_id": 123,
                                "cpu_percent": 75.0,
                            }
                        ],
                        "sampled_processes": 10,
                        "skipped_processes": 0,
                        "truncated": False,
                        "duration_ms": 100.0,
                    }
                },
            ),
        ),
        "workstation-01",
    )


def test_concise_terminal_hides_process_identity() -> None:
    console = Console(record=True, width=120, color_system=None)

    show_check(_attributed_report().results[0], console)

    rendered = console.export_text()
    assert "1 CPU contributor(s) captured (Complete)" in rendered
    assert "worker.exe" not in rendered
    assert "123" not in rendered


def test_terminal_details_render_process_attribution() -> None:
    console = Console(record=True, width=120, color_system=None)

    show_check_details(_attributed_report().results[0], console)

    rendered = console.export_text()
    assert "Top CPU Contributors" in rendered
    assert "worker.exe" in rendered
    assert "123" in rendered
    assert "75.0" in rendered


def test_export_reporters_render_process_attribution_readably() -> None:
    report = _attributed_report()

    markdown = render_markdown(report)
    html = render_html(report)

    assert "### Top CPU contributors" in markdown
    assert "| worker.exe | 123 | 75.0 |" in markdown
    assert "worker.exe" in html
    assert "<th>CPU %</th>" in html
    assert "&#34;process_name&#34;" not in html
