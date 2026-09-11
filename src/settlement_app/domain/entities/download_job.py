# -*- coding: utf-8 -*-
"""DownloadJob 엔티티 — branch + domain에 대한 Playwright 스크래퍼 실행 하나를 추적."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum


class JobStatus(str, Enum):
    CREATED   = "created"
    RUNNING   = "running"
    COMPLETED = "completed"   # 로컬에 저장 완료
    ERROR     = "error"
    FORCE_COMPLETED = "force_completed"  # 수동 강제 완료


@dataclass
class DownloadJob:
    """
    branch + domain에 대해 ScraperHost에 할당된 엑셀 다운로드 태스크 하나.

    생명주기: CREATED → RUNNING → COMPLETED | ERROR
              ERROR | CREATED → FORCE_COMPLETED  (수동)
              ERROR → CREATED (재시도 시 새 job 레코드 생성; 기존 레코드 변경 금지)
    """
    job_id: str
    scraper_host_id: str
    branch_code: str          # 예: "yeouido_01"
    domain: str               # "baemin" | "coupang"
    target_date: datetime.date
    status: JobStatus = JobStatus.CREATED
    current_step: str = "created"
    progress_pct: int = 0
    started_at: datetime.datetime | None = None
    finished_at: datetime.datetime | None = None
    file_count: int = 0
    error_count: int = 0
    error_message: str | None = None
    # 성공적으로 다운로드된 파일 경로 목록 (settings.excel_download_dir 기준 상대 경로)
    downloaded_files: list[str] = field(default_factory=list)
