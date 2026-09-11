# -*- coding: utf-8 -*-
"""엑셀 다운로드 페이지와 스크래퍼 워커에서 사용하는 DTO."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DownloadJobRow:
    """엑셀 다운로드 작업 대기열 테이블의 행 하나."""
    job_id: str
    scraper_host_id: str
    branch_code: str
    domain: str
    current_step: str
    progress_pct: int
    started_at: str      # 표시용 문자열 또는 "-"
    finished_at: str
    file_count: int
    error_count: int
    status: str          # badge 색조 키
    status_label: str


@dataclass(frozen=True)
class ScraperHostHeartbeatRow:
    scraper_host_id: str
    current_task: str    # "branch_code / domain" 또는 "idle"
    heartbeat_ago: str   # 표시용 문자열, 예: "3초 전"
    status: str          # badge 색조 키
    status_label: str


@dataclass(frozen=True)
class DownloadRunConfig:
    target_date: datetime.date
    download_dir: str     # 표시용 str 경로; 실제 코드에서는 pathlib.Path 사용
    domains: list[str] = field(default_factory=list)
