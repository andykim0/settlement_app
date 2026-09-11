# -*- coding: utf-8 -*-
"""
ScraperWorker — Qt 전역 스레드 풀에서 Scraper.download_excel() 호출 하나를
실행하는 QRunnable.

스레딩 계약:
  - ScraperWorker.run()은 스레드 풀 스레드에서 실행.
  - UI에 표시되는 모든 상태 변경은 메인 스레드에 위치한 RunRegistry를 경유.
  - RunWorkerSignals(QObject) 인스턴스는 반드시 메인 스레드에서 생성하여
    QRunnable 생성자에 전달해야 함(make_worker() 참조).
    signals QObject가 메인 스레드에 위치하므로, Qt가 모든 .emit() 호출을
    자동으로 QueuedConnection으로 메인 스레드에 마샬링 — invokeMethod 수동 호출 불필요.

시그널 흐름:
  worker.signals.started     → registry.on_worker_started
  worker.signals.progress    → registry.on_worker_progress
  worker.signals.log_line    → registry.on_worker_log
  worker.signals.completed   → registry.on_worker_completed
  worker.signals.failed      → registry.on_worker_failed
"""
from __future__ import annotations

import datetime
import logging
import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from settlement_app.application.services.run_registry import RunRegistry
from settlement_app.application.services.scraper_protocol import Scraper
from settlement_app.application.dto.run_state import RunState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 시그널 캐리어 — 반드시 메인 스레드에서 생성해야 함
# ---------------------------------------------------------------------------

class RunWorkerSignals(QObject):
    """
    워커 스레드에서 ScraperWorker가 방출하는 시그널.

    이 QObject가 메인 스레드에서 생성되므로, Qt는 (풀 스레드에서의 호출 포함)
    모든 .emit() 호출을 QueuedConnection을 통해 메인 스레드로 라우팅.
    """

    # run_id
    started: Signal = Signal(str)
    # run_id, step, pct
    progress: Signal = Signal(str, str, int)
    # run_id, line
    log_line: Signal = Signal(str, str)
    # run_id, file_paths (list[str])
    completed: Signal = Signal(str, list)
    # run_id, error_message
    failed: Signal = Signal(str, str)


# ---------------------------------------------------------------------------
# QRunnable
# ---------------------------------------------------------------------------

class ScraperWorker(QRunnable):
    """
    하나의 (source) 엑셀 다운로드 실행을 위한 백그라운드 워커.

    메인 스레드에서 생성; run()은 풀 스레드에서 실행.
    run()에서 UI 메서드나 레지스트리 메서드를 직접 호출하지 말 것 —
    시그널 방출만 허용.

    `signals`는 주입 방식(여기서 생성하지 않음)으로 QObject의 스레드 친화성이
    호출자 스레드에 의해 결정되도록 하여, 메인 스레드 요구사항을 관례가 아닌
    명시적 계약으로 만듦.
    """

    def __init__(
        self,
        run_state: RunState,
        scraper: Scraper,
        signals: RunWorkerSignals,
        output_dir: str,
        target_date: datetime.date,
        branch_code: str,
    ) -> None:
        super().__init__()
        self.run_state = run_state
        self.scraper = scraper
        self.signals = signals
        self.output_dir = output_dir
        self.target_date = target_date
        self.branch_code = branch_code
        self.setAutoDelete(True)

    def run(self) -> None:
        run_id = self.run_state.run_id

        def on_progress(step: str, pct: int) -> None:
            self.signals.progress.emit(run_id, step, pct)

        try:
            self.signals.started.emit(run_id)
            logger.info(
                "ScraperWorker starting: run_id=%s source=%s branch=%s",
                run_id, self.run_state.source, self.branch_code,
            )
            self.signals.log_line.emit(
                run_id,
                f"Starting {self.run_state.source} download for branch={self.branch_code} "
                f"date={self.target_date.isoformat()}",
            )
            file_paths = self.scraper.download_excel(
                branch_code=self.branch_code,
                target_date=self.target_date,
                output_dir=self.output_dir,
                on_progress=on_progress,
            )
            logger.info(
                "ScraperWorker completed: run_id=%s files=%s",
                run_id, file_paths,
            )
            self.signals.completed.emit(run_id, file_paths)

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.error(
                "ScraperWorker failed: run_id=%s error=%s\n%s",
                run_id, error_msg, traceback.format_exc(),
            )
            self.signals.failed.emit(run_id, error_msg)


# ---------------------------------------------------------------------------
# 팩토리 — 페이지 핸들러에서 연결 로직을 분리
# ---------------------------------------------------------------------------

def make_worker(
    run_state: RunState,
    scraper: Scraper,
    registry: RunRegistry,
    output_dir: str,
    target_date: datetime.date,
    branch_code: str,
) -> ScraperWorker:
    """
    ScraperWorker를 생성하고 시그널을 레지스트리에 연결.

    메인 스레드에서 호출. 반환된 워커는 이후
    QThreadPool.globalInstance().start(worker)에 제출 가능.
    """
    # 호출자 스레드(메인)에서 signals를 생성해야 Qt가 풀 스레드의 emit을
    # QueuedConnection으로 메인 스레드에 전달한다.
    signals = RunWorkerSignals()
    signals.started.connect(registry.on_worker_started)
    signals.progress.connect(registry.on_worker_progress)
    signals.log_line.connect(registry.on_worker_log)
    signals.completed.connect(registry.on_worker_completed)
    signals.failed.connect(registry.on_worker_failed)

    return ScraperWorker(
        run_state=run_state,
        scraper=scraper,
        signals=signals,
        output_dir=output_dir,
        target_date=target_date,
        branch_code=branch_code,
    )
