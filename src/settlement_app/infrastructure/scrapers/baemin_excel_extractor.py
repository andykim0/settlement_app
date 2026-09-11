# baemin_excel_extractor.py
# =========================
# 배민커넥트비즈 포털의 모든 협력사를 순회하며 어제 날짜의
# 배달처리비 엑셀 보고서를 다운로드합니다.
#
# 진입 가정:
#   로그인 + OTP 이후 '협력사를 선택해주세요' 페이지에 도착하며,
#   아직 어떤 협력사도 활성화되지 않은 상태입니다. 항상 각 협력사로 전환합니다.
#
# 협력사별 처리 흐름:
#   1. switch_to_partner: 드롭다운 열기, 옵션 클릭, 선택 완료 클릭
#   2. /center/delivery-fee-download 로 이동
#   3. DatePicker 열기, 필요 시 어제 날짜의 월로 이동,
#      어제 날짜를 두 번 클릭(시작 = 종료), 적용 클릭
#   4. 엑셀 다운로드 클릭 → 사유 입력 모달 열림
#   5. 사유 "일일정산" 입력, 모달 내 엑셀 다운로드 클릭
#   6. 다운로드된 파일 저장
#
# 사용법:
#     from playwright.async_api import async_playwright
#     from baemin_excel_extractor import extract_all_partners_excels
#
#     await extract_all_partners_excels(page, save_dir="./excels")

from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional

from playwright.async_api import (
    Download,
    Page,
    TimeoutError as PWTimeout,
)


# ----- 설정 ----------------------------------------------------------------

BASE_URL = "https://deliverycenter.baemin.com"

PARTNER_CHANGE_URL = f"{BASE_URL}/center/change"
DELIVERY_FEE_DOWNLOAD_URL = f"{BASE_URL}/center/delivery-fee-download"

DOWNLOAD_REASON_TEXT = "일일정산"

# 협력사 선택 셀렉터
PARTNER_SELECT_BUTTON = (
    'button[aria-haspopup="dialog"][data-atelier-component^="Select"]'
)
PARTNER_SELECT_HIDDEN = 'article select[aria-hidden="true"][tabindex="-1"]'
SUBMIT_BUTTON_TEXT = "선택 완료"

# DatePicker 셀렉터
DATE_PICKER_TRIGGER = '[data-atelier-component="DatePicker.Trigger"]'
DATE_PICKER_DIALOG = '[role="dialog"][data-atelier-component="DatePicker"]'
PREV_MONTH_BUTTON = 'button[aria-label="이전 달"]'
NEXT_MONTH_BUTTON = 'button[aria-label="다음 달"]'
DATE_PICKER_CAPTION = "caption"  # "2026년 5월"
APPLY_BUTTON_TEXT = "적용"

EXCEL_DOWNLOAD_BUTTON_TEXT = "엑셀 다운로드"

PARTNER_ID_PATTERN = re.compile(r"DP\d+")
CAPTION_PATTERN = re.compile(r"(\d{4})년\s*(\d{1,2})월")


# ----- 1단계: 협력사 ID 목록 가져오기 --------------------------------------

async def get_partner_ids(page: Page) -> list[str]:
    # /center/change 페이지의 숨겨진 <select> 에서 모든 협력사 ID
    # (예: 'DP2502044374') 를 추출합니다. 클릭은 필요 없습니다.
    await page.goto(PARTNER_CHANGE_URL)
    try:
        await page.wait_for_selector(PARTNER_SELECT_HIDDEN, timeout=15000)
    except PWTimeout as e:
        raise RuntimeError(
            "협력사 변경 페이지의 hidden <select>를 찾지 못했습니다. "
            "로그인 상태와 URL을 확인하세요."
        ) from e

    partner_ids: list[str] = await page.locator(PARTNER_SELECT_HIDDEN).first.evaluate(
        """sel => Array.from(sel.options)
            .map(o => o.value.trim())
            .filter(Boolean)"""
    )
    print(f"[+] 발견된 협력사 ID: {partner_ids}")
    return partner_ids


# ----- 2단계: 특정 협력사로 전환 -------------------------------------------

async def switch_to_partner(page: Page, partner_id: str) -> None:
    # 협력사 드롭다운을 열고, `partner_id` 옵션을 클릭한 뒤 선택 완료를 누릅니다.
    print(f"[~] {partner_id} 협력사로 전환 중...")
    await page.goto(PARTNER_CHANGE_URL)
    await page.wait_for_selector(PARTNER_SELECT_BUTTON, timeout=15000)
    await page.locator(PARTNER_SELECT_BUTTON).first.click()

    await page.wait_for_selector('[role="dialog"] [role="listbox"]', timeout=10000)

    option = page.locator(f'[role="option"][id$="/{partner_id}"]')
    await option.wait_for(state="visible", timeout=5000)
    await option.click()

    await page.get_by_role("button", name=SUBMIT_BUTTON_TEXT).click()

    try:
        await page.wait_for_url(
            lambda url: "/center/change" not in url,
            timeout=10000,
        )
    except PWTimeout:
        await asyncio.sleep(1)

    print(f"[+] {partner_id} 활성화 완료.")


# ----- 3단계: DatePicker — 어제 날짜를 시작과 종료로 설정 ------------------

async def _read_visible_month(page: Page) -> Optional[tuple[int, int]]:
    # 캘린더 헤더에 현재 표시된 (연도, 월) 을 읽습니다.
    # 캡션 형식: "2026년 5월"
    caption = page.locator(DATE_PICKER_DIALOG).locator(DATE_PICKER_CAPTION).first
    text = await caption.inner_text()
    match = CAPTION_PATTERN.search(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


async def _navigate_to_month(page: Page, target_year: int, target_month: int) -> None:
    # 캘린더가 target_year/target_month 를 표시할 때까지 이전/다음 달 버튼을 클릭합니다.
    # 안전 한도: 24회 클릭 (2년).
    dialog = page.locator(DATE_PICKER_DIALOG)

    for _ in range(24):
        current = await _read_visible_month(page)
        if current is None:
            raise RuntimeError("DatePicker 월 표시를 읽지 못했습니다.")

        cur_year, cur_month = current
        if cur_year == target_year and cur_month == target_month:
            return

        # 월 차이 계산; 음수이면 이전으로 이동해야 함
        diff = (target_year - cur_year) * 12 + (target_month - cur_month)
        if diff < 0:
            await dialog.locator(PREV_MONTH_BUTTON).click()
        else:
            await dialog.locator(NEXT_MONTH_BUTTON).click()
        # 캘린더 재렌더링을 위한 짧은 대기
        await asyncio.sleep(0.2)

    raise RuntimeError(
        f"DatePicker에서 {target_year}년 {target_month}월로 이동하지 못했습니다."
    )


async def _set_date_range_yesterday(page: Page, target_date: date) -> None:
    # DatePicker 를 열고, target_date 의 월로 이동한 뒤, 해당 일을
    # 두 번 클릭(시작 == 종료) 하고 적용을 눌러 확정합니다.
    print(f"[~] DatePicker 열기 → {target_date.isoformat()} 선택")

    # 1. DatePicker 열기
    trigger = page.locator(DATE_PICKER_TRIGGER).first
    await trigger.wait_for(state="visible", timeout=10000)
    await trigger.click()

    # 2. 다이얼로그 대기
    dialog = page.locator(DATE_PICKER_DIALOG)
    await dialog.wait_for(state="visible", timeout=10000)

    # 3. 필요한 경우 해당 월로 이동
    await _navigate_to_month(page, target_date.year, target_date.month)

    # 4. 해당 일을 두 번 클릭 (시작 선택 후 종료 선택 → 1일 범위)
    # 비활성화된 오늘/미래 버튼은 :not([disabled]) 로 필터링
    day_button = dialog.locator(
        f'button[aria-label="{target_date.day}일"]:not([disabled])'
    ).first
    await day_button.wait_for(state="visible", timeout=5000)
    await day_button.click()
    await asyncio.sleep(0.2)
    await day_button.click()
    await asyncio.sleep(0.2)

    # 5. 적용 버튼을 눌러 확정
    apply_button = dialog.get_by_role("button", name=APPLY_BUTTON_TEXT)
    await apply_button.click()

    # 다이얼로그가 닫힐 때까지 대기
    await dialog.wait_for(state="hidden", timeout=5000)
    print(f"[+] 날짜 적용 완료: {target_date.isoformat()}")


# ----- 4단계: 엑셀 다운로드 ------------------------------------------------

async def _go_to_delivery_fee_download(page: Page) -> None:
    # 배달처리비 다운로드 페이지로 직접 이동합니다.
    await page.goto(DELIVERY_FEE_DOWNLOAD_URL)
    await page.wait_for_load_state("domcontentloaded")
    # DatePicker 트리거가 렌더링될 때까지 대기 — 페이지가 상호작용 가능한
    # 상태가 되었음을 보여주는 가장 강력한 신호입니다.
    await page.locator(DATE_PICKER_TRIGGER).first.wait_for(
        state="visible", timeout=15000
    )


async def _click_excel_download(page: Page, *, in_dialog: bool = False) -> None:
    # "엑셀 다운로드" 버튼을 클릭합니다.
    #   - in_dialog=False: 페이지의 버튼 → 사유 입력 모달이 열림
    #   - in_dialog=True: 모달 내부의 버튼 → 실제 다운로드가 시작됨
    if in_dialog:
        scope = page.locator('[role="dialog"]:not([data-atelier-component="DatePicker"])')
        await scope.first.wait_for(state="visible", timeout=10000)
        button = scope.get_by_role("button", name=EXCEL_DOWNLOAD_BUTTON_TEXT)
    else:
        button = page.get_by_role("button", name=EXCEL_DOWNLOAD_BUTTON_TEXT)
    await button.first.wait_for(state="visible", timeout=15000)
    await button.first.click()


async def _fill_reason(page: Page, reason: str) -> None:
    # 사유 입력 모달(DatePicker 모달이 아님) 내부에 사유를 입력합니다.
    # 일반적인 입력 패턴들을 차례로 시도합니다.
    dialog = page.locator(
        '[role="dialog"]:not([data-atelier-component="DatePicker"])'
    ).first
    await dialog.wait_for(state="visible", timeout=10000)

    candidates = [
        dialog.locator("textarea"),
        dialog.locator('input[placeholder*="사유"]'),
        dialog.locator('input[type="text"]'),
        dialog.get_by_role("textbox"),
    ]
    for candidate in candidates:
        try:
            if await candidate.count() > 0 and await candidate.first.is_visible():
                await candidate.first.fill(reason)
                return
        except Exception:
            continue
    raise RuntimeError("사유 입력 필드를 찾지 못했습니다.")


async def download_excel(
    page: Page,
    partner_id: str,
    target_date: date,
    save_dir: Path,
    reason: str = DOWNLOAD_REASON_TEXT,
) -> Optional[Path]:
    # 배달처리비 다운로드 페이지에서의 처리 흐름:
    #   1. /center/delivery-fee-download 로 이동.
    #   2. DatePicker 열기, target_date 를 시작과 종료로 선택, 적용.
    #   3. "엑셀 다운로드" 클릭 → 사유 입력 모달 열림.
    #   4. 사유 필드 입력.
    #   5. 모달 내 "엑셀 다운로드" 클릭 → 파일 다운로드 시작.
    save_dir.mkdir(parents=True, exist_ok=True)

    # 1. 페이지 이동
    print(f"[~] {partner_id} 배달처리비 다운로드 페이지로 이동...")
    try:
        await _go_to_delivery_fee_download(page)
    except PWTimeout:
        print(f"[!] {partner_id} 배달처리비 다운로드 페이지 로딩 실패.")
        return None

    # 2. 어제 날짜로 범위 설정 (시작 == 종료)
    try:
        await _set_date_range_yesterday(page, target_date)
    except (PWTimeout, RuntimeError) as e:
        print(f"[!] {partner_id} 날짜 설정 실패: {e}")
        return None

    # 3. 페이지의 엑셀 다운로드 클릭 → 사유 입력 모달 열림
    print(f"[~] {partner_id} 엑셀 다운로드 버튼 클릭 → 사유 입력 모달 대기...")
    try:
        await _click_excel_download(page, in_dialog=False)
    except PWTimeout:
        print(f"[!] {partner_id} '엑셀 다운로드' 버튼을 찾지 못했습니다.")
        return None

    # 4. 사유 입력
    try:
        await _fill_reason(page, reason)
        print(f"[~] {partner_id} 사유 '{reason}' 입력 완료.")
    except (PWTimeout, RuntimeError) as e:
        print(f"[!] {partner_id} 사유 입력 실패: {e}")
        return None

    # 5. 모달 내 엑셀 다운로드 클릭 → 실제 다운로드 시작
    print(f"[~] {partner_id} 모달 내 엑셀 다운로드 클릭 → 파일 수신 대기...")
    async with page.expect_download(timeout=60000) as dl_info:
        await _click_excel_download(page, in_dialog=True)
    download: Download = await dl_info.value

    suggested = download.suggested_filename or f"{partner_id}.xlsx"
    out_path = save_dir / f"{partner_id}_{target_date.isoformat()}_{suggested}"
    await download.save_as(out_path)
    print(f"[+] 다운로드 완료: {out_path.name}")
    return out_path


# ----- 5단계: 오케스트레이터 -----------------------------------------------

async def extract_all_partners_excels(
    page: Page,
    target_date: Optional[date] = None,
    save_dir: str | Path = "./excels",
    only: Optional[Iterable[str]] = None,
) -> list[Path]:
    # 로그인된 계정이 접근할 수 있는 모든 협력사를 처리합니다.
    #
    # `target_date`: 다운로드할 단일 날짜. 기본값은 어제.
    # `only`: 처리 대상을 제한할 협력사 ID 목록 (테스트용, 선택).
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    save_dir = Path(save_dir)

    # 모든 협력사 ID 가져오기
    all_partner_ids = await get_partner_ids(page)

    if only is not None:
        wanted = set(only)
        all_partner_ids = [pid for pid in all_partner_ids if pid in wanted]

    if not all_partner_ids:
        raise RuntimeError("처리할 협력사 ID가 없습니다.")

    print(f"[~] {len(all_partner_ids)}개 협력사 처리 시작.")
    print(f"    대상 날짜: {target_date.isoformat()}")
    print(f"    순서: {' → '.join(all_partner_ids)}")

    results: list[Path] = []
    failures: list[tuple[str, str]] = []

    for i, partner_id in enumerate(all_partner_ids, start=1):
        print(f"\n--- ({i}/{len(all_partner_ids)}) 협력사 {partner_id} ---")
        try:
            await switch_to_partner(page, partner_id)
            path = await download_excel(page, partner_id, target_date, save_dir)
            if path is not None:
                results.append(path)
            else:
                failures.append((partner_id, "다운로드 실패 (로그 참조)"))
        except Exception as e:
            print(f"[!] {partner_id} 실패: {e}")
            failures.append((partner_id, str(e)))
            continue

    print(
        f"\n[+] 완료: {len(results)}개 다운로드, {len(failures)}개 실패."
    )
    if failures:
        print("실패 목록:")
        for partner_id, error_msg in failures:
            print(f"  - {partner_id}: {error_msg}")
    return results
