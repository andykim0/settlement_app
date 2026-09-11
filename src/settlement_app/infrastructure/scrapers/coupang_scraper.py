# -*- coding: utf-8 -*-
"""
CoupangScraper — coupang_core.py를 감싸 Scraper 프로토콜을 충족하는 어댑터.

워커가 임포트하는 클래스. Playwright 자동화 로직은 coupang_core.py에 유지 —
이 파일은 통합 경계 역할만 수행.
"""
from __future__ import annotations

import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from settlement_app.application.services.scraper_protocol import ScraperProgress
from settlement_app.infrastructure.scrapers.coupang_core import run_scrape
from settlement_app.infrastructure.scrapers.coupang_imap_otp import (
    get_app_password,
    load_accounts,
)
from settlement_app.infrastructure.settings.app_settings import AppSettings


class CoupangScraper:
    """
    동기 Coupang 스크래퍼.

    자격증명은 AppSettings를 통해 주입 — 절대 하드코딩하지 않음.
    워커는 백그라운드 스레드(QRunnable 경유)에서 download_excel()을 호출.
    """

    domain: str = "coupang"

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
        하나의 지사에 대해 전체 Coupang 로그인 → 다운로드 흐름 실행.

        반환값: 저장된 파일의 절대 경로.
        인증 실패 시 RuntimeError 발생.
        """
        scraper_cfg = self._settings.scrapers
        if not scraper_cfg.coupang_id:
            raise RuntimeError(
                "coupang_id is not configured. "
                "Set scrapers.coupang_id in ~/.settlement_app/config.json"
            )
        self._check_email_auth_ready(scraper_cfg.coupang_id)
        download_path = Path(output_dir) / branch_code / "coupang"

        with sync_playwright() as pw:
            return run_scrape(
                pw,
                coupang_id=scraper_cfg.coupang_id,
                coupang_pw=self._get_coupang_pw(),
                download_dir=download_path,
                target_date=target_date,
                on_progress=on_progress,
            )

    @staticmethod
    def _check_email_auth_ready(coupang_id: str) -> None:
        # IMAP OTP는 계정이 등록되어 있어야 하며 (메타데이터:
        # ~/.coupang_imap_otp/accounts.json), OS 키체인에 앱 비밀번호가
        # 저장되어 있어야 한다. Playwright 실행 전에 조기 실패 처리.
        accounts = load_accounts()
        account = accounts.get(coupang_id)
        if account is None:
            raise RuntimeError(
                f"IMAP 계정이 등록되지 않았습니다 (coupang_id={coupang_id!r}).\n"
                f"`python -m settlement_app.infrastructure.scrapers."
                f"coupang_imap_otp register` 로 등록하세요."
            )
        if account.status != "active":
            raise RuntimeError(
                f"IMAP 계정 상태가 active 가 아닙니다 "
                f"(coupang_id={coupang_id!r}, status={account.status!r}, "
                f"last_error={account.last_error!r})"
            )
        if not get_app_password(account.email):
            raise RuntimeError(
                f"키체인에 앱 비밀번호가 없습니다 ({account.email}). "
                f"`python -m settlement_app.infrastructure.scrapers."
                f"coupang_imap_otp register` 로 재등록하세요."
            )

    def _get_coupang_pw(self) -> str:
        # OS 키체인을 우선 조회 (권장); `export COUPANG_PW`를 사용하는
        # 환경과의 하위 호환성을 위해 환경변수로 fallback.
        import keyring
        import os
        pw = keyring.get_password("settlement_app", "COUPANG_PW")
        if pw:
            return pw
        pw = os.environ.get("COUPANG_PW", "")
        if pw:
            return pw
        raise RuntimeError(
            "COUPANG_PW 가 설정되지 않았습니다. 다음 중 하나를 수행하세요:\n"
            "  1) 키체인에 저장 (권장, 한 번만):\n"
            "     python3 -c \"import keyring; keyring.set_password("
            "'settlement_app', 'COUPANG_PW', '비밀번호')\"\n"
            "  2) 환경변수로 임시 설정:\n"
            "     export COUPANG_PW='비밀번호'"
        )
