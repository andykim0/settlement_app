# -*- coding: utf-8 -*-
"""
원본 대비 변경 사항:
  - 최상위 `with sync_playwright() as playwright: run(playwright)` 실행 블록 제거
  - `run(playwright)` → 모듈 수준 상수(COUPANG_ID, COUPANG_PW, COUPANG_DOWNLOAD_DIR) 대신
    자격증명과 출력 디렉터리를 주입받도록 변경
  - on_progress 콜백 파라미터 추가
  - coupang_email_verifier_v1_2 임포트는 여전히 런타임에 필요 —
    sys.path에 포함되어 있는지 확인(원본과 같은 디렉터리 또는 설치된 경우)

run_scrape() 내부의 Playwright 자동화 로직은 실제 coupang 파트너 포털에 대해
재테스트하지 않은 채 수정하지 말 것.
"""
from __future__ import annotations

import datetime
import random
from pathlib import Path
from typing import Callable

from playwright.sync_api import Page, Playwright


# 쿠팡 부정 방지 시스템에 덜 기계적으로 보이도록 페이지 전환마다
# 2~5초 무작위 일시정지를 삽입. 페이지 로드/네비게이션을 유발하는
# 동작 이후, 다음 상호작용 이전에 사용.
_PAUSE_MIN_MS = 2000
_PAUSE_MAX_MS = 5000


def _human_pause(page: Page) -> None:
    page.wait_for_timeout(random.randint(_PAUSE_MIN_MS, _PAUSE_MAX_MS))

# IMAP 기반 OTP 조회. 제목/본문 추출 방식은 레거시 coupang_email_verifier_v1_2와
# 동일 (한국어/영어 제목 힌트, \b\d{6}\b 본문 정규식).
# 설정/인증정보 위치: ~/.coupang_imap_otp/accounts.json (메타데이터),
# OS 키체인 (앱 비밀번호).
from .coupang_imap_otp import get_code_for_coupang_id


def run_scrape(
    playwright: Playwright,
    *,
    coupang_id: str,
    coupang_pw: str,
    download_dir: Path,
    target_date: datetime.date | None = None,
    on_progress: Callable[[str, int], None] | None = None,
) -> list[str]:
    """
    Coupang Eats 파트너 포털 스크래핑 실행.

    반환값: 저장된 파일 경로 목록(문자열).
    로그인 실패 시 RuntimeError 발생(원본과 동일).
    탐색/다운로드 실패 시 Playwright 오류 발생.

    매개변수는 원본 스크립트의 모듈 수준 상수를 그대로 반영하므로
    내부 로직은 변경되지 않음 — 호출 경계만 다름.
    """
    if target_date is None:
        target_date = datetime.date.today() - datetime.timedelta(days=1)

    yesterday_iso = target_date.isoformat()

    def _progress(step: str, pct: int) -> None:
        if on_progress:
            on_progress(step, pct)

    _progress("launch_browser", 5)
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    try:
        _progress("navigate_login", 10)
        page.goto(
            "https://xauth.coupang.com/auth/realms/eats-partner/protocol/openid-connect/auth"
            "?client_id=edp-vendor-portal"
            "&redirect_uri=https%3A%2F%2Fpartner.coupangeats.com%2F"
            "&state=ab881f3f-f431-42f1-85b2-e3998443e403"
            "&response_mode=fragment&response_type=code&scope=openid%20eats-partner"
            "&nonce=41b7efda-5b02-48a7-b4ac-95a6d684348d"
            "&code_challenge=ooa7h_dSc0BvXS7-qQVZiAZ9xZobk5hccI7X5Nxso5M"
            "&code_challenge_method=S256"
        )
        _human_pause(page)  # 로그인 페이지가 안정될 때까지 대기, 읽는 것처럼 보이게

        page.get_by_role("textbox", name="아이디 입력").click()
        page.get_by_role("textbox", name="아이디 입력").fill(coupang_id)
        page.get_by_role("textbox", name="비밀번호 입력").click()
        page.get_by_role("textbox", name="비밀번호 입력").fill(coupang_pw)
        page.get_by_role("button", name="로그인").click()
        _progress("login_submitted", 20)

        auth_tab = page.get_by_role("tab", name="이메일로 인증")
        try:
            auth_tab.wait_for(state="visible", timeout=10000)
        except Exception:
            raise RuntimeError(
                "로그인 실패: 아이디 또는 비밀번호가 올바르지 않습니다. "
                "입력값을 확인한 뒤 다시 실행해 주세요."
            )

        auth_tab.click()
        _human_pause(page)  # 인증 탭 열림, OTP 요청 전 대기
        request_time = datetime.datetime.now()
        page.get_by_role("button", name="인증코드 전송").click()
        _progress("otp_requested", 35)

        verification_code = get_code_for_coupang_id(
            coupang_id,
            request_time=request_time,
        )
        _progress("otp_received", 50)

        page.get_by_role("textbox", name="이메일로 발송된 인증코드 입력").click()
        page.get_by_role("textbox", name="이메일로 발송된 인증코드 입력").fill(verification_code)
        page.get_by_role("button", name="인증 완료").click()
        _progress("auth_complete", 60)

        page.wait_for_selector('a[href="/page/settlement-download"]', timeout=20000)
        page.locator('a[href="/page/settlement-download"]').click()
        page.wait_for_url("**/page/settlement-download", timeout=20000)
        page.wait_for_selector(
            ".custom-picker-input-content .ant-picker", timeout=20000
        )
        _progress("settlement_page_loaded", 70)

        page.locator(".custom-picker-input-content .ant-picker").first.click()
        page.wait_for_selector(
            ".ant-picker-dropdown:not(.ant-picker-dropdown-hidden) .ant-picker-content",
            timeout=10000,
        )
        page.wait_for_timeout(400)

        page.locator(
            f'.ant-picker-dropdown:not(.ant-picker-dropdown-hidden) '
            f'td[title="{yesterday_iso}"]:not(.ant-picker-cell-disabled) '
            f'.ant-picker-cell-inner'
        ).first.click()
        _progress("date_selected", 80)

        page.wait_for_timeout(1500)
        page.wait_for_selector('a:has-text("전체 파일 받기")', state="visible", timeout=20000)

        _progress("download_starting", 88)
        with page.expect_download(timeout=60000) as download_info:
            page.get_by_role("link", name="전체 파일 받기").click()

        download = download_info.value

        download_dir.mkdir(parents=True, exist_ok=True)
        suggested = download.suggested_filename or f"{coupang_id}_{yesterday_iso}.zip"
        out_path = download_dir / f"{coupang_id}_{yesterday_iso}_{suggested}"
        download.save_as(str(out_path))
        _progress("saved_to_local", 100)

        return [str(out_path)]

    except Exception:
        # 사용자가 브라우저를 수동으로 확인하지 않아도 쿠팡 플로우의 어느 지점에서
        # 실패했는지 디버깅할 수 있도록 스크린샷 + URL + 제목을 캡처.
        try:
            debug_dir = Path.home() / ".settlement_app" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            shot = debug_dir / f"coupang_fail_{ts}.png"
            page.screenshot(path=str(shot), full_page=True)
            print(f"[!] Failure screenshot: {shot}")
            print(f"[!] Page URL: {page.url}")
            try:
                print(f"[!] Page title: {page.title()}")
            except Exception:
                pass
        except Exception as shot_err:
            print(f"[!] Could not capture debug info: {shot_err}")
        raise

    finally:
        context.close()
        browser.close()
