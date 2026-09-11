# -*- coding: utf-8 -*-
"""
BaeminScraper — baemin_core.py를 감싸 Scraper 프로토콜을 충족하는 어댑터.

이 어댑터는 QRunnable 워커가 호출하는 동기 Scraper 프로토콜과 호환되도록
워커 스레드 내 새 이벤트 루프에서 비동기 코루틴을 실행.
"""
from __future__ import annotations

import asyncio
import datetime
import os
from pathlib import Path

from playwright.async_api import async_playwright

from settlement_app.application.services.scraper_protocol import ScraperProgress
from settlement_app.infrastructure.scrapers.baemin_core import run_scrape
from settlement_app.infrastructure.settings.app_settings import AppSettings


class BaeminScraper:
    """
    비동기 Baemin 스크래퍼를 감싸는 동기 인터페이스 어댑터.

    자격증명은 AppSettings를 통해 주입.
    워커는 백그라운드 스레드(QRunnable 경유)에서 download_excel()을 호출.
    """

    domain: str = "baemin"

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def download_excel(
        self,
        branch_code: str,
        target_date: datetime.date,
        output_dir: str,
        on_progress: ScraperProgress | None = None,
    ) -> list[str]:
        """
        동기 진입점 — 새 이벤트 루프에서 비동기 스크래퍼를 실행.

        중요: 반드시 워커 스레드에서만 호출. Qt 메인 스레드에서는 절대 호출 금지.
        """
        cfg = self._settings.scrapers
        if not cfg.baemin_id:
            raise RuntimeError(
                "baemin_id is not configured. "
                "Set scrapers.baemin_id in ~/.settlement_app/config.json"
            )
        excel_save_dir = Path(output_dir) / branch_code / "baemin"

        sms_keywords: tuple[str, ...] = tuple(
            kw.strip()
            for kw in os.environ.get("SMS_KEYWORDS", "").split(",")
            if kw.strip()
        )

        async def _run() -> list[str]:
            async with async_playwright() as pw:
                return await run_scrape(
                    pw,
                    baemin_id=cfg.baemin_id,
                    baemin_pw=self._get_baemin_pw(),
                    sms_host=cfg.sms_server_host,
                    sms_port=cfg.sms_server_port,
                    sms_keywords=sms_keywords,
                    otp_timeout=cfg.otp_timeout_seconds,
                    excel_save_dir=excel_save_dir,
                    target_date=target_date,
                    on_progress=on_progress,
                )

        # 새 이벤트 루프에서 실행 — 비메인 스레드이므로 안전
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()

    def _get_baemin_pw(self) -> str:
        # TODO: 암호화된 keyring / AES 키 파일에서 로드
        pw = os.environ.get("BAEMIN_PASSWORD", "")
        if not pw:
            raise RuntimeError(
                "BAEMIN_PASSWORD environment variable not set. "
                "Set it before launching the app."
            )
        return pw
