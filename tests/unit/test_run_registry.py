# -*- coding: utf-8 -*-
"""
RunRegistry 상태 관리에 대한 단위 테스트.

dict 기반 상태 로직만 테스트.
슬롯 메서드를 직접 테스트하므로(큐드 커넥션이 메인 스레드에서
호출하는 방식을 시뮬레이션) Qt 이벤트 루프 불필요.
"""
from __future__ import annotations

import pytest

# RunRegistry는 QObject이므로 단위 테스트에서도 QObject 인스턴스화 전에
# QCoreApplication이 존재해야 한다.
from PySide6.QtCore import QCoreApplication
import sys


@pytest.fixture(scope="module")
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


@pytest.fixture
def registry(qt_app):
    from settlement_app.application.services.run_registry import RunRegistry
    return RunRegistry()


# ---------------------------------------------------------------------------
# register_run
# ---------------------------------------------------------------------------

def test_register_run_creates_queued_state(registry):
    from settlement_app.application.dto.run_state import RunStatus
    state = registry.register_run(source="coupang")
    assert state.run_id in [r.run_id for r in registry.list_runs()]
    assert state.status == RunStatus.QUEUED
    assert state.source == "coupang"


def test_register_run_custom_id(registry):
    state = registry.register_run(source="baemin", run_id="baemin-test-001")
    assert state.run_id == "baemin-test-001"
    assert registry.get_run("baemin-test-001") is state


def test_register_multiple_runs_are_independent(registry):
    s1 = registry.register_run(source="coupang")
    s2 = registry.register_run(source="baemin")
    assert s1.run_id != s2.run_id


# ---------------------------------------------------------------------------
# on_worker_started
# ---------------------------------------------------------------------------

def test_on_worker_started_transitions_to_running(registry):
    from settlement_app.application.dto.run_state import RunStatus
    state = registry.register_run(source="coupang")
    registry.on_worker_started(state.run_id)
    assert state.status == RunStatus.RUNNING
    assert state.started_at is not None


def test_on_worker_started_unknown_id_is_no_op(registry):
    registry.on_worker_started("no-such-id")  # 예외가 발생하면 안 됨


# ---------------------------------------------------------------------------
# on_worker_progress
# ---------------------------------------------------------------------------

def test_on_worker_progress_updates_step_and_pct(registry):
    state = registry.register_run(source="coupang")
    registry.on_worker_started(state.run_id)
    registry.on_worker_progress(state.run_id, "login_started", 10)
    assert state.progress_step == "login_started"
    assert state.progress_pct == 10


# ---------------------------------------------------------------------------
# on_worker_completed
# ---------------------------------------------------------------------------

def test_on_worker_completed_transitions_to_succeeded(registry):
    from settlement_app.application.dto.run_state import RunStatus
    state = registry.register_run(source="baemin")
    registry.on_worker_started(state.run_id)
    registry.on_worker_completed(state.run_id, ["/tmp/baemin.xlsx"])
    assert state.status == RunStatus.SUCCEEDED
    assert state.output_file_paths == ["/tmp/baemin.xlsx"]
    assert state.finished_at is not None


# ---------------------------------------------------------------------------
# on_worker_failed
# ---------------------------------------------------------------------------

def test_on_worker_failed_transitions_to_failed(registry):
    from settlement_app.application.dto.run_state import RunStatus
    state = registry.register_run(source="coupang")
    registry.on_worker_started(state.run_id)
    registry.on_worker_failed(state.run_id, "RuntimeError: login failed")
    assert state.status == RunStatus.FAILED
    assert "login failed" in (state.error_message or "")
    assert state.finished_at is not None


# ---------------------------------------------------------------------------
# tail_logs
# ---------------------------------------------------------------------------

def test_tail_logs_returns_last_n_lines(registry):
    state = registry.register_run(source="coupang")
    for i in range(10):
        registry.on_worker_log(state.run_id, f"line {i}")
    lines = registry.tail_logs(state.run_id, n=3)
    assert len(lines) == 3
    assert lines[-1] == "line 9"


def test_tail_logs_unknown_id_returns_empty(registry):
    assert registry.tail_logs("no-such-id") == []


# ---------------------------------------------------------------------------
# 로그 링 버퍼 상한
# ---------------------------------------------------------------------------

def test_log_ring_buffer_capped_at_200(registry):
    state = registry.register_run(source="baemin")
    for i in range(250):
        registry.on_worker_log(state.run_id, f"line {i}")
    assert len(state.last_log_lines) == 200
    lines = list(state.last_log_lines)
    assert lines[0] == "line 50"   # 가장 오래된 항목이 유지됨
    assert lines[-1] == "line 249"


# ---------------------------------------------------------------------------
# runtime_seconds
# ---------------------------------------------------------------------------

def test_runtime_seconds_is_none_before_start(registry):
    state = registry.register_run(source="coupang")
    assert state.runtime_seconds is None


def test_runtime_seconds_is_positive_after_start(registry):
    state = registry.register_run(source="coupang")
    registry.on_worker_started(state.run_id)
    assert state.runtime_seconds is not None
    assert state.runtime_seconds >= 0.0
