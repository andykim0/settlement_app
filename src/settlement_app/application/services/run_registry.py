# -*- coding: utf-8 -*-
"""
RunRegistry — 스크래퍼 실행 상태를 위한 중앙 인메모리 레지스트리.

Qt 메인 스레드에 위치(MainWindow에서 생성). 엑셀 다운로드 페이지와
모니터링 페이지 모두 동일한 인스턴스를 참조하며 시그널을 구독.

스레딩 모델:
  - ScraperWorker는 QThreadPool 스레드에서 실행.
  - 워커는 RunSignalEmitter(메인 스레드에서 생성된 QObject)를 보유.
  - 워커가 emitter.signals.*를 호출하면 Qt가 emitter가 생성된 메인 스레드로
    QueuedConnection을 통해 자동 마샬링.
  - RunRegistry 슬롯(on_worker_*)은 RunState를 갱신하고
    UI가 연결하는 상위 레벨 시그널을 재방출.

TODO: 재시작 후에도 실행 이력이 유지되도록 DynamoDB 영속화 연결점 추가.
      레지스트리에 Callable[[RunState], None] 영속화 콜백을 주입 —
      기본값은 no-op이며 시작 시 교체 가능. 실행 상태는 휘발성이 높고
      상태/지사 키 기반 조회가 잦아 DynamoDB가 적합 (관계형 데이터는 PostgreSQL).
"""
from __future__ import annotations

import logging
import uuid
from typing import Callable

from PySide6.QtCore import QObject, Signal

from settlement_app.application.dto.run_state import RunState, RunStatus, _now

logger = logging.getLogger(__name__)


class RunRegistry(QObject):
    """
    현재 앱 세션의 모든 RunState 인스턴스를 소유하는 싱글턴형 QObject.

    시그널
    ------
    run_added(run_id: str)
        새 실행이 등록될 때(status=QUEUED) 방출.
    run_status_changed(run_id: str, status: str)
        실행이 새 상태로 전환될 때 방출.
    run_log_appended(run_id: str, line: str)
        실행에 대한 단일 로그 라인이 캡처될 때 방출.
    run_progress_updated(run_id: str, step: str, pct: int)
        스크래퍼가 진행률 틱을 보고할 때 방출.
    """

    run_added: Signal = Signal(str)
    run_status_changed: Signal = Signal(str, str)
    run_log_appended: Signal = Signal(str, str)
    run_progress_updated: Signal = Signal(str, str, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # run_id → RunState; 메인 스레드에서만 변경
        self._runs: dict[str, RunState] = {}

    # ------------------------------------------------------------------
    # 공개 읽기 API (메인 스레드에서 언제든 호출 가능)
    # ------------------------------------------------------------------

    def list_runs(self) -> list[RunState]:
        """알려진 모든 실행의 스냅샷 목록 반환 (최신 항목이 마지막)."""
        return list(self._runs.values())

    def get_run(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)

    def tail_logs(self, run_id: str, n: int = 50) -> list[str]:
        """해당 실행의 마지막 *n*줄 로그 반환."""
        state = self._runs.get(run_id)
        if state is None:
            return []
        lines = list(state.last_log_lines)
        return lines[-n:]

    # ------------------------------------------------------------------
    # 등록
    # ------------------------------------------------------------------

    def register_run(
        self,
        source: str,
        branch_code: str = "",
        run_id: str | None = None,
    ) -> RunState:
        """
        새 QUEUED RunState를 생성하고 등록.

        워커를 스레드 풀에 제출하기 전에 메인 스레드(예: 버튼 핸들러)에서 호출.
        branch_code: 이 실행이 속한 지사 코드 (예: 'Ridestar').
        """
        if run_id is None:
            run_id = f"{source}-{_now().astimezone().date().isoformat()}-{uuid.uuid4().hex[:6]}"
        state = RunState(run_id=run_id, source=source, branch_code=branch_code)
        self._runs[run_id] = state
        logger.debug(
            "RunRegistry: registered run %s source=%s branch=%s",
            run_id, source, branch_code,
        )
        self.run_added.emit(run_id)
        return state

    # ------------------------------------------------------------------
    # 슬롯 — 워커 시그널 연결을 통해 호출됨 (QueuedConnection,
    # Qt가 자동으로 메인 스레드에 마샬링).
    # ------------------------------------------------------------------

    def on_worker_started(self, run_id: str) -> None:
        """실행 상태를 RUNNING으로 전환."""
        state = self._runs.get(run_id)
        if state is None:
            logger.warning("RunRegistry.on_worker_started: unknown run_id=%s", run_id)
            return
        state.status = RunStatus.RUNNING
        state.started_at = _now()
        self._append_log(run_id, f"[{state.started_at.astimezone().strftime('%H:%M:%S')}] run started")
        self.run_status_changed.emit(run_id, RunStatus.RUNNING.value)

    def on_worker_progress(self, run_id: str, step: str, pct: int) -> None:
        """진행 단계와 퍼센트 갱신."""
        state = self._runs.get(run_id)
        if state is None:
            return
        state.progress_step = step
        state.progress_pct = pct
        self._append_log(run_id, f"[{_now().astimezone().strftime('%H:%M:%S')}] {step} ({pct}%)")
        self.run_progress_updated.emit(run_id, step, pct)

    def on_worker_log(self, run_id: str, line: str) -> None:
        """원시 로그 라인 추가."""
        self._append_log(run_id, line)

    def on_worker_completed(self, run_id: str, file_paths: list) -> None:
        """실행 상태를 SUCCEEDED로 전환하고 출력 경로 기록."""
        state = self._runs.get(run_id)
        if state is None:
            logger.warning("RunRegistry.on_worker_completed: unknown run_id=%s", run_id)
            return
        state.status = RunStatus.SUCCEEDED
        state.finished_at = _now()
        state.output_file_paths = list(file_paths)
        ts = state.finished_at.astimezone().strftime("%H:%M:%S")
        self._append_log(run_id, f"[{ts}] succeeded — {len(file_paths)} file(s)")
        self.run_status_changed.emit(run_id, RunStatus.SUCCEEDED.value)

    def on_worker_failed(self, run_id: str, error_message: str) -> None:
        """실행 상태를 FAILED로 전환하고 오류 기록."""
        state = self._runs.get(run_id)
        if state is None:
            logger.warning("RunRegistry.on_worker_failed: unknown run_id=%s", run_id)
            return
        state.status = RunStatus.FAILED
        state.finished_at = _now()
        state.error_message = error_message
        ts = state.finished_at.astimezone().strftime("%H:%M:%S")
        self._append_log(run_id, f"[{ts}] FAILED: {error_message}")
        self.run_status_changed.emit(run_id, RunStatus.FAILED.value)

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _append_log(self, run_id: str, line: str) -> None:
        state = self._runs.get(run_id)
        if state is not None:
            state.last_log_lines.append(line)
        self.run_log_appended.emit(run_id, line)
