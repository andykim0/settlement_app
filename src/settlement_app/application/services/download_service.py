# -*- coding: utf-8 -*-
"""DownloadService — 엑셀 다운로드 작업 오케스트레이션 스텁.

TODO: 실제 구현은 ScraperWorker 스레드를 큐에 넣고
      DownloadJobRepository를 통해 DownloadJob 행을 영속화함.
"""
from __future__ import annotations

import datetime

from settlement_app.application.dto.download_dto import DownloadJobRow, ScraperHostHeartbeatRow


class DownloadService:
    def list_jobs_for_date(self, target_date: datetime.date) -> list[DownloadJobRow]:
        # TODO: DownloadJobRepository.list_by_date(target_date) 결과 반환
        return [
            DownloadJobRow("JOB-001", "HOST-01", "yeouido_01", "baemin",
                           "download_excel", 72, "13:12", "-", 1, 0, "info", "실행 중"),
            DownloadJobRow("JOB-002", "HOST-02", "guro_03",    "baemin",
                           "auth_code_timeout", 44, "13:07", "13:11", 0, 1, "danger", "에러"),
            DownloadJobRow("JOB-003", "HOST-03", "seocho_05",  "coupang",
                           "created", 0, "-", "-", 0, 0, "neutral", "대기"),
            DownloadJobRow("JOB-004", "HOST-01", "mapo_02",    "coupang",
                           "saved_to_local", 100, "12:54", "12:59", 2, 0, "success", "실행완료"),
        ]

    def get_scraper_host_heartbeats(self) -> list[ScraperHostHeartbeatRow]:
        # TODO: ScraperHostHeartbeatRepository.list_live() 조회
        return [
            ScraperHostHeartbeatRow("HOST-01", "yeouido_01 / baemin", "3초 전", "info",   "RUNNING"),
            ScraperHostHeartbeatRow("HOST-02", "guro_03 / baemin",    "9초 전", "danger", "ERROR"),
        ]
