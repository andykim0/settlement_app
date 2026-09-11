# -*- coding: utf-8 -*-
"""설정 페이지 — 7개 중 7번째."""
from __future__ import annotations

import socket

from PySide6.QtWidgets import QGridLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from settlement_app.infrastructure.settings.app_settings import AppSettings
from settlement_app.presentation.widgets.badge import badge_cell
from settlement_app.presentation.widgets.cards import Card
from settlement_app.presentation.widgets.table import FlatTable
from settlement_app.presentation.widgets.pages._scaffold import page_header, page_scaffold


def _lbl(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("fieldLabel")
    return lbl


class SettingsPage(QWidget):
    def __init__(
        self,
        settings: AppSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings

        page, box = page_scaffold()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        box.addWidget(page_header(
            "설정",
            "PostgreSQL, 스크립트, NAS, DynamoDB, ScraperHost 장비 설정을 관리합니다",
        ))

        grid = QGridLayout()
        grid.setSpacing(16)

        # --- PostgreSQL --------------------------------------------------
        # TODO: SettingsService.save_db_config()을 호출하는 "저장" 버튼 추가
        pg = Card("PostgreSQL 연결")
        pg_form = QGridLayout()
        pg_form.setHorizontalSpacing(16)
        pg_form.setVerticalSpacing(12)
        pg_form.addWidget(_lbl("Host"),          0, 0)
        pg_form.addWidget(QLineEdit(settings.db.host), 0, 1)
        pg_form.addWidget(_lbl("SSL Mode"),       0, 2)
        pg_form.addWidget(QLineEdit(settings.db.sslmode), 0, 3)
        pg_form.addWidget(_lbl("Shared DB"),      1, 0)
        pg_form.addWidget(QLineEdit(settings.db.shared_database), 1, 1)
        pg_form.addWidget(_lbl("Rider DB"),       1, 2)
        pg_form.addWidget(QLineEdit(settings.db.rider_database), 1, 3)
        pg_form.addWidget(_lbl("AES 키 위치"),    2, 0)
        pg_form.addWidget(QLineEdit(settings.db.aes_key_path), 2, 1, 1, 3)
        pg_form.setColumnStretch(1, 1)
        pg_form.setColumnStretch(3, 1)
        pg.body.addLayout(pg_form)
        grid.addWidget(pg, 0, 0)

        # --- 도메인 스크립트 ----------------------------------------------
        # TODO: ScraperRegistry / settings에서 스크립트 레지스트리 로드; 경로 편집 허용
        dom = Card("도메인별 스크립트")
        dt = FlatTable(["도메인", "스크립트", "상태"])
        dt.setMinimumHeight(170)
        dt.add_row(["baemin",  "scripts/playwright/baemin.py",  badge_cell("사용",      "success")])
        dt.add_row(["coupang", "scripts/playwright/coupang.py", badge_cell("사용",      "success")])
        dt.add_row(["요기요",   "scripts/playwright/yogiyo.py",  badge_cell("추가 예정", "warning")])
        dom.body.addWidget(dt)
        grid.addWidget(dom, 0, 1)

        # --- 저장/전송 설정 --------------------------------------------
        st = Card("저장/전송 설정")
        sg = QGridLayout()
        sg.setHorizontalSpacing(16)
        sg.setVerticalSpacing(12)
        sg.addWidget(_lbl("로컬/NAS 경로"),  0, 0)
        sg.addWidget(QLineEdit(settings.storage.local_excel_dir), 0, 1, 1, 3)
        sg.addWidget(_lbl("S3 Bucket"),      1, 0)
        sg.addWidget(QLineEdit(settings.storage.s3_bucket), 1, 1, 1, 3)
        sg.setColumnStretch(1, 1)
        sg.setColumnStretch(3, 1)
        st.body.addLayout(sg)
        grid.addWidget(st, 1, 0)

        # --- ScraperHost 목록 ------------------------------------------------
        # TODO: ScraperHostRegistryService.list_scraper_hosts()로 채우기
        # 현재는 이 앱이 실행 중인 로컬 PC 1대만 표시.
        wk = Card("ScraperHost 장비 목록")
        wt = FlatTable(["ScraperHost", "지원 도메인", "OTP 수신", "상태"])
        wt.setMinimumHeight(170)
        host_id = socket.gethostname() or "HOST-LOCAL"
        wt.add_row([
            host_id,
            "baemin, coupang",
            "-",                       # OTP 수신 방식 미추적 — 추후 설정에서 관리
            badge_cell("온라인", "success"),  # 이 앱이 이 PC에서 실행 중이므로 온라인
        ])
        wk.body.addWidget(wt)
        grid.addWidget(wk, 1, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        box.addLayout(grid)

        # --- 기본값 테이블 ----------------------------------------------
        # TODO: 편집 지원 시 SettingsService를 통해 변경사항 저장
        defaults = Card("실행 기본값")
        dt2 = FlatTable(["옵션", "값", "설명"])
        dt2.setMinimumHeight(220)
        sc = settings.scrapers
        dt2.add_row(["동시 실행 ScraperHost 수", f"{sc.max_concurrent_workers}",  "로컬 PC 성능 기준 기본 병렬도"])
        dt2.add_row(["도메인별 재시도",     f"{sc.retry_count}회",           "인증/다운로드 실패 시 지사·도메인 단위 재시도"])
        dt2.add_row(["Step timeout",        f"{sc.step_timeout_seconds}초",  "로그인/인증/다운로드 각 단계 제한"])
        dt2.add_row(["로그 보관",           f"{sc.log_retention_days}일",    "진행/완료/에러 로그를 날짜별 디렉토리로 보관"])
        defaults.body.addWidget(dt2)
        box.addWidget(defaults)
        box.addStretch()
