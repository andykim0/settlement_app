# -*- coding: utf-8 -*-
"""
스크래퍼 프로토콜 — 모든 도메인 스크래퍼가 반드시 충족해야 하는 인터페이스.

구체 구현체는 infrastructure/scrapers/에 위치.
workers/의 워커는 이 인터페이스를 호출 — 스크래퍼를 직접 임포트하지 않음.
"""
from __future__ import annotations

import datetime
from typing import Callable, Protocol


class ScraperProgress(Protocol):
    """진행률 보고를 위해 스크래퍼에 주입되는 콜백 타입."""
    def __call__(self, step: str, pct: int) -> None: ...


class Scraper(Protocol):
    """
    도메인 스크래퍼(baemin / coupang / ...)를 위한 Protocol.

    구현체는 동기 또는 비동기 — 호출자(워커)가 백그라운드 스레드/태스크에서
    실행 방식을 결정.
    """

    @property
    def domain(self) -> str:
        """도메인 식별자, 예: 'baemin' 또는 'coupang'."""
        ...

    def download_excel(
        self,
        branch_code: str,
        target_date: datetime.date,
        output_dir: str,
        on_progress: ScraperProgress | None = None,
    ) -> list[str]:
        """
        전체 로그인 → 탐색 → 다운로드 흐름 실행.

        반환값: 저장된 파일 경로 목록(절대 경로 문자열).
        로그인/OTP 실패 시 AuthenticationError 발생.
        기타 복구 불가 오류 시 DownloadJobError 발생.
        """
        ...
