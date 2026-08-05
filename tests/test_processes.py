from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import psutil
import pytest

from shuri.checks import cpu, memory, processes
from shuri.models import CheckResult, CheckStatus, ScoreDeduction
from shuri.models.cpu import CpuSnapshot


class FakeProcess:
    def __init__(
        self,
        process_id: int,
        name: str,
        *,
        cpu_percent: float = 0.0,
        resident_bytes: int = 0,
        inaccessible: bool = False,
        exits_after_prime: bool = False,
    ) -> None:
        self.info = {
            "pid": process_id,
            "name": name,
            "memory_info": SimpleNamespace(rss=resident_bytes),
        }
        self._cpu_percent = cpu_percent
        self._cpu_calls = 0
        self._inaccessible = inaccessible
        self._exits_after_prime = exits_after_prime

    def cpu_percent(self, interval: float | None = None) -> float:
        del interval
        self._cpu_calls += 1
        if self._inaccessible:
            raise psutil.AccessDenied(self.info["pid"])
        if self._exits_after_prime and self._cpu_calls > 1:
            raise psutil.NoSuchProcess(self.info["pid"])
        return 0.0 if self._cpu_calls == 1 else self._cpu_percent


def _process_iterator(items: list[FakeProcess]) -> Iterator[FakeProcess]:
    return iter(items)


def test_cpu_attribution_is_sorted_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_processes = [
        FakeProcess(index, f"process-{index}", cpu_percent=float(index)) for index in range(1, 9)
    ]
    monkeypatch.setattr(processes.os, "getpid", lambda: 999)
    monkeypatch.setattr(
        processes.psutil, "process_iter", lambda attrs: _process_iterator(fake_processes)
    )

    attribution = processes.collect_cpu_process_attribution(sample_interval=0)

    assert attribution["state"] == "complete"
    assert len(attribution["contributors"]) == processes.MAX_CONTRIBUTORS
    assert [item["process_id"] for item in attribution["contributors"]] == [8, 7, 6, 5, 4]
    assert set(attribution["contributors"][0]) == {
        "process_name",
        "process_id",
        "cpu_percent",
    }


def test_memory_attribution_is_sorted_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_processes = [
        FakeProcess(index, f"process-{index}", resident_bytes=index * 100) for index in range(1, 9)
    ]
    monkeypatch.setattr(processes.os, "getpid", lambda: 999)
    monkeypatch.setattr(
        processes.psutil, "process_iter", lambda attrs: _process_iterator(fake_processes)
    )
    monkeypatch.setattr(processes.psutil, "virtual_memory", lambda: SimpleNamespace(total=10_000))

    attribution = processes.collect_memory_process_attribution()

    assert attribution["state"] == "complete"
    assert len(attribution["contributors"]) == processes.MAX_CONTRIBUTORS
    assert [item["process_id"] for item in attribution["contributors"]] == [8, 7, 6, 5, 4]
    assert attribution["contributors"][0]["memory_percent"] == 8.0


def test_inaccessible_process_makes_attribution_partial_without_aborting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_processes = [
        FakeProcess(10, "protected", inaccessible=True),
        FakeProcess(11, "available", cpu_percent=25.0),
    ]
    monkeypatch.setattr(processes.os, "getpid", lambda: 999)
    monkeypatch.setattr(
        processes.psutil, "process_iter", lambda attrs: _process_iterator(fake_processes)
    )

    attribution = processes.collect_cpu_process_attribution(sample_interval=0)

    assert attribution["state"] == "partial"
    assert attribution["skipped_processes"] == 1
    assert attribution["contributors"][0]["process_name"] == "available"


def test_process_scan_limit_marks_evidence_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_processes = [FakeProcess(index, f"process-{index}") for index in range(1, 5)]
    monkeypatch.setattr(processes.os, "getpid", lambda: 999)
    monkeypatch.setattr(
        processes.psutil, "process_iter", lambda attrs: _process_iterator(fake_processes)
    )
    monkeypatch.setattr(processes.psutil, "virtual_memory", lambda: SimpleNamespace(total=10_000))

    attribution = processes.collect_memory_process_attribution(max_processes=2)

    assert attribution["state"] == "partial"
    assert attribution["sampled_processes"] == 2
    assert attribution["truncated"] is True


def test_exited_process_is_skipped_without_losing_other_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_processes = [
        FakeProcess(10, "short-lived", exits_after_prime=True),
        FakeProcess(11, "available", cpu_percent=20.0),
    ]
    monkeypatch.setattr(processes.os, "getpid", lambda: 999)
    monkeypatch.setattr(
        processes.psutil, "process_iter", lambda attrs: _process_iterator(fake_processes)
    )

    attribution = processes.collect_cpu_process_attribution(sample_interval=0)

    assert attribution["state"] == "partial"
    assert attribution["skipped_processes"] == 1
    assert [item["process_name"] for item in attribution["contributors"]] == ["available"]


def test_cpu_budget_reserves_time_for_measurement(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_processes = [FakeProcess(10, "worker", cpu_percent=25.0)]
    moments = iter((0.0, 0.1, 0.2, 0.65, 0.7))
    monkeypatch.setattr(processes, "perf_counter", lambda: next(moments, 0.7))
    monkeypatch.setattr(processes, "sleep", lambda duration: None)
    monkeypatch.setattr(processes.os, "getpid", lambda: 999)
    monkeypatch.setattr(
        processes.psutil, "process_iter", lambda attrs: _process_iterator(fake_processes)
    )

    attribution = processes.collect_cpu_process_attribution(time_budget=0.75, sample_interval=0.1)

    assert attribution["contributors"][0]["process_name"] == "worker"
    assert attribution["contributors"][0]["cpu_percent"] == 25.0


def test_unexpected_enumeration_failure_returns_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_attrs: object) -> Iterator[FakeProcess]:
        raise RuntimeError("platform race")

    monkeypatch.setattr(processes.psutil, "process_iter", fail)

    attribution = processes.collect_memory_process_attribution()

    assert attribution["state"] == "unavailable"
    assert attribution["contributors"] == []


def test_attribution_never_changes_status_or_scoring() -> None:
    deduction = ScoreDeduction("CPU usage is above 85%", 5, "cpu")
    original = CheckResult(
        "cpu",
        "CPU",
        CheckStatus.WARNING,
        "Elevated",
        deductions=(deduction,),
    )

    attached = processes.attach_process_attribution(
        original,
        {
            "state": "unavailable",
            "contributors": [],
        },
    )

    assert attached.status is CheckStatus.WARNING
    assert attached.deductions == (deduction,)
    assert "pressure result is unchanged" in attached.findings[-1]


def test_healthy_cpu_does_not_collect_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cpu.psutil, "cpu_freq", lambda: None)
    monkeypatch.setattr(cpu.psutil, "cpu_count", lambda logical: 8 if logical else 4)
    monkeypatch.setattr(cpu.psutil, "cpu_percent", lambda interval: 10.0)
    monkeypatch.setattr(cpu.platform, "processor", lambda: "Test CPU")
    monkeypatch.setattr(cpu.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        cpu,
        "collect_cpu_process_attribution",
        lambda: pytest.fail("healthy CPU must not collect process evidence"),
    )

    result = cpu.check_cpu()

    assert result.status is CheckStatus.PASS
    assert "process_attribution" not in result.metrics


def test_elevated_cpu_collects_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cpu.psutil, "cpu_freq", lambda: None)
    monkeypatch.setattr(cpu.psutil, "cpu_count", lambda logical: 8 if logical else 4)
    monkeypatch.setattr(cpu.psutil, "cpu_percent", lambda interval: 90.0)
    monkeypatch.setattr(cpu.platform, "processor", lambda: "Test CPU")
    monkeypatch.setattr(cpu.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        cpu,
        "collect_cpu_process_attribution",
        lambda: {"state": "complete", "contributors": []},
    )

    result = cpu.check_cpu()

    assert result.status is CheckStatus.WARNING
    assert result.metrics["process_attribution"]["state"] == "complete"


def test_healthy_memory_does_not_collect_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        memory.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=100, available=50, used=50),
    )
    monkeypatch.setattr(
        memory.psutil,
        "swap_memory",
        lambda: SimpleNamespace(total=100, used=0),
    )
    monkeypatch.setattr(
        memory,
        "collect_memory_process_attribution",
        lambda: pytest.fail("healthy memory must not collect process evidence"),
    )

    result = memory.check_memory()

    assert result.status is CheckStatus.PASS
    assert "process_attribution" not in result.metrics


def test_pure_cpu_assessment_remains_unchanged() -> None:
    result = cpu.build_cpu_result(CpuSnapshot("Test CPU", "x86_64", 4, 8, 10.0, 3200.0), None)

    assert result.status is CheckStatus.PASS
    assert "process_attribution" not in result.metrics
