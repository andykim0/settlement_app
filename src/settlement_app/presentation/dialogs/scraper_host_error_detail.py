# -*- coding: utf-8 -*-
"""ScraperHostErrorDetailPanel — 엑셀 다운로드 및 모니터링 페이지에 표시되는 사이드바 패널."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from settlement_app.presentation.theme import COLOR
from settlement_app.presentation.widgets.badge import Badge
from settlement_app.presentation.widgets.buttons import make_button
from settlement_app.presentation.widgets.table import FlatTable


class ScraperHostErrorDetailPanel(QFrame):
    """Figma의 'ScraperHost / 에러 상세 패널' 사이드바."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(10)

        title = QLabel("ScraperHost / 에러 상세 패널")
        title.setObjectName("cardTitle")
        sub = QLabel(
            "모니터링 화면 오른쪽에 dock 형태로 붙는 상세 패널입니다. "
            "스크래퍼 호스트, 지사, 도메인, 단계, 로그 파일, 재실행 기준을 한 번에 보여줍니다."
        )
        sub.setWordWrap(True)
        sub.setObjectName("mutedNote")
        v.addWidget(title)
        v.addWidget(sub)

        head = QHBoxLayout()
        big = QLabel("HOST-02")
        big.setStyleSheet(
            f"font-size:22px; font-weight:700; color:{COLOR['text']};"
        )
        head.addWidget(big)
        head.addWidget(Badge("ERROR", "danger"))
        head.addStretch()
        v.addLayout(head)

        # TODO: 에러 로그 테이블에서 행 선택 시 MonitoringPage로부터
        #       전달받은 ScraperHostErrorDetailDTO로 채우기
        t = FlatTable(["항목", "값"])
        t.setMinimumHeight(220)
        # FIXME: 로그 경로 하드코딩 — settings.log_base_dir / 날짜 / scraper_host_id로 도출해야 함
        t.add_row(["지사/도메인",  "guro_03 / baemin"])
        t.add_row(["실패 구분",   "Excel Download 실패"])
        t.add_row(["단계",       "auth_code_timeout"])
        t.add_row(["로그 파일",   "logs/2026-05-13/HOST-02/guro_03_baemin_error.log"])
        t.add_row(["재실행 단위",  "ScraperHost ID + 지사 + 도메인"])
        v.addWidget(t)

        btns = QHBoxLayout()
        # TODO: "재실행"을 ExcelDownloadUseCase.retry_job(scraper_host_id, branch_code, domain)에 연결
        btns.addWidget(make_button("해당 지사/도메인 재실행", "primary"))
        # TODO: "로그 파일 열기"를 FilesystemService.open_log_file(log_path)에 연결
        #       QDesktopServices.openUrl 또는 subprocess 사용 — 이벤트 루프를 절대 차단하지 말 것
        btns.addWidget(make_button("로그 파일 열기", "secondary"))
        btns.addStretch()
        v.addLayout(btns)
