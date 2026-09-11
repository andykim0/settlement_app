# -*- coding: utf-8 -*-
"""
EnqueueDownloadRunUseCase

DownloadJob 행을 생성하고 ScraperWorker 스레드를 디스패치.
이 유스케이스가 다운로드 실행을 시작하는 유일한 진입점.
실제 Playwright 로직은 infrastructure/scrapers/에 위치.
"""
from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from settlement_app.domain.entities.download_job import DownloadJob, JobStatus


@dataclass
class EnqueueDownloadRunResult:
    job_ids: list[str]
    queued_count: int


class EnqueueDownloadRunUseCase:
    """
    모든(또는 선택된) branch+domain 쌍에 대해 다운로드 실행을 큐에 추가.

    아직 미구현 — 의도된 인터페이스를 보여주기 위한 스텁.
    """

    def execute(
        self,
        target_date: datetime.date,
        output_dir: str,
        branch_codes: list[str] | None = None,   # None = 모든 활성 지사
    ) -> EnqueueDownloadRunResult:
        # TODO: 1. DataImportService에서 활성 BranchDomainAccount 목록 로드
        # TODO: 2. (branch, domain) 쌍마다 repository를 통해 DownloadJob 행 생성
        # TODO: 3. 각 job당 ScraperWorker (QRunnable) 한 개를 QThreadPool에 제출
        # TODO: 4. UI가 상태를 폴링할 수 있도록 job ID 목록 반환
        raise NotImplementedError(
            "EnqueueDownloadRunUseCase not yet implemented. "
            "Wire up DownloadJobRepository and ScraperWorker first."
        )
