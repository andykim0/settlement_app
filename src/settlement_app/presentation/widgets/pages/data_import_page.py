# -*- coding: utf-8 -*-
"""데이터 가져오기 페이지 — 7개 중 2번째."""
from __future__ import annotations

import socket
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QVBoxLayout, QWidget

from settlement_app.presentation.widgets.badge import badge_cell
from settlement_app.presentation.widgets.buttons import make_button
from settlement_app.presentation.widgets.cards import Card
from settlement_app.presentation.widgets.table import FlatTable
from settlement_app.presentation.widgets.pages._scaffold import page_header, page_scaffold

if TYPE_CHECKING:
    from settlement_app.infrastructure.settings.app_settings import AppSettings


def _scraper_host_id() -> str:
    """현재 머신의 호스트명을 반환. 빈 경우 'HOST-LOCAL' 폴백."""
    return socket.gethostname() or "HOST-LOCAL"


class DataImportPage(QWidget):
    def __init__(
        self,
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        page, box = page_scaffold()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        # TODO: "지사 도메인 가져오기"를 DataImportService.fetch_branches_from_db()에 연결
        #       QThread에서 실행해야 함 (네트워크 I/O로 이벤트 루프를 차단하지 말 것)
        box.addWidget(page_header(
            "데이터 가져오기",
            "PostgreSQL에서 지사, 도메인 계정, 납부 항목, ScraperHost 매핑을 가져옵니다",
            make_button("지사 도메인 가져오기", "primary"),
        ))

        card = Card("가져온 지사별 도메인 계정")
        # TODO: 정적 행을 DataImportService의 BranchAccountDTO 목록으로 교체
        # NOTE: "인증 대상" 컬럼 — 실제 데이터 흐름 시 뒤 4자리만 표시하도록 마스킹 필요
        t = FlatTable(["지사 ID", "지사명", "도메인", "인증 방식", "인증 대상",
                       "ScraperHost ID", "계정 상태"])
        t.setMinimumHeight(280)

        # 설정에서 활성 지사 코드 및 도메인 계정을 읽어 행 생성.
        # 현재 단일 사용자 모드: baemin/coupang 각 1행씩, 총 2행.
        branch_code = settings.scrapers.active_branch_code
        host_id = _scraper_host_id()
        t.add_row([
            branch_code, branch_code, "baemin",
            "-",                           # 인증 방식 미추적 — 추후 설정에서 관리
            settings.scrapers.baemin_id or "-",
            host_id,
            badge_cell("활성", "success"),
        ])
        t.add_row([
            branch_code, branch_code, "coupang",
            "-",                           # 인증 방식 미추적 — 추후 설정에서 관리
            settings.scrapers.coupang_id or "-",
            host_id,
            badge_cell("활성", "success"),
        ])

        card.body.addWidget(t)
        box.addWidget(card)
        box.addStretch()
