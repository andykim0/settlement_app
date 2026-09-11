# -*- coding: utf-8 -*-
"""
원본 대비 변경 사항:
  - 최상위 `asyncio.run(main())` 실행 블록 제거
  - `run(playwright)` → `run_scrape(playwright, *, baemin_id, baemin_pw, ...)` 로 변경하여
    모듈 수준 상수 대신 자격증명, SMS 서버 설정, 출력 디렉터리를 주입받도록 수정
  - on_progress 콜백 파라미터 추가
  - server.sms_otp_waiter 및 baemin_excel_extractor 임포트는 여전히 런타임에 필요함.
    TODO: 위 두 모듈을 이 파일과 함께 infrastructure/scrapers/ 아래로 패키징할 것.

run_scrape() 내부의 Playwright 자동화 로직은 실제 배민 배달대행 포털에 대해
재테스트하지 않은 채 수정하지 말 것.
"""
from __future__ import annotations

import asyncio
import datetime
from pathlib import Path
from typing import Callable, Iterable

from playwright.async_api import Playwright

try:
    # 상대 임포트: server/ 패키지는 현재 infrastructure/scrapers/server/ 아래에 위치
    from .server.sms_otp_waiter import SmsOtpWaiter  # type: ignore[import]
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "server.sms_otp_waiter not found. "
        "Expected at infrastructure/scrapers/server/sms_otp_waiter.py"
    ) from exc

try:
    # 상대 임포트: 헬퍼는 현재 이 파일과 같은 infrastructure/scrapers/ 경로에 위치
    from .baemin_excel_extractor import extract_all_partners_excels  # type: ignore[import]
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "baemin_excel_extractor not found. "
        "Expected at infrastructure/scrapers/baemin_excel_extractor.py"
    ) from exc


async def run_scrape(
    playwright: Playwright,
    *,
    baemin_id: str,
    baemin_pw: str,
    sms_host: str,
    sms_port: int,
    sms_keywords: tuple[str, ...],
    otp_timeout: int,
    excel_save_dir: Path,
    target_date: datetime.date | None = None,
    on_progress: Callable[[str, int], None] | None = None,
) -> list[str]:
    """
    비동기 Baemin 배달대행 센터 스크래핑.

    반환값: 저장된 Excel 파일 경로 목록(문자열).
    자격증명이 비어 있으면 RuntimeError 발생.
    실패 시 Playwright 또는 SmsOtpWaiter 예외 발생.
    """

    def _progress(step: str, pct: int) -> None:
        if on_progress:
            on_progress(step, pct)

    if not baemin_id.strip():
        raise RuntimeError("BAEMIN_ID is empty — set it via AppSettings.")
    if not baemin_pw.strip():
        raise RuntimeError("BAEMIN_PASSWORD is empty — set it via AppSettings.")

    _progress("launch_browser", 5)
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()

    try:
        _progress("navigate_login", 10)
        await page.goto(
            "https://biz-member.baemin.com/login"
            "?returnUrl=https%3A%2F%2Fdeliverycenter.baemin.com"
        )

        await page.get_by_test_id("id").click()
        await page.get_by_test_id("id").fill(baemin_id)
        await page.get_by_test_id("password").click()
        await page.get_by_test_id("password").fill(baemin_pw)
        await page.get_by_role("button", name="로그인").click()
        _progress("login_submitted", 20)

        # "인증번호 받기" 클릭 전에 SMS OTP 대기자 시작
        _progress("sms_waiter_start", 30)
        with SmsOtpWaiter(
            host=sms_host,
            port=sms_port,
            keyword_filters=sms_keywords,
        ) as otp_waiter:
            await page.get_by_role("button", name="인증번호 받기").click()
            _progress("otp_requested", 40)

            otp_result = await asyncio.to_thread(
                otp_waiter.wait_for_code, otp_timeout
            )
            _progress("otp_received", 55)

            await page.get_by_role("textbox", name="인증번호").click()
            await page.get_by_role("textbox", name="인증번호").fill(otp_result.code)

        await page.get_by_role("button", name="인증번호 확인").click()
        _progress("auth_complete", 65)

        # 협력사 순회 + 엑셀 다운로드를 baemin_excel_extractor에 위임
        excel_save_dir.mkdir(parents=True, exist_ok=True)
        results = await extract_all_partners_excels(
            page,
            target_date=target_date,    # None이면 어제 날짜 사용
            save_dir=excel_save_dir,
            only=None,
        )
        _progress("saved_to_local", 100)

        try:
            await page.get_by_role("button", name="로그아웃").click()
        except Exception:
            pass  # 로그아웃 버튼이 없을 수 있음; 무시해도 안전

        return [str(p) for p in results]

    finally:
        await context.close()
        await browser.close()
