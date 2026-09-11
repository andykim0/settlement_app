# -*- coding: utf-8 -*-
"""RunAllConfirmDialog — 전체 프로세스 실행 확인."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from settlement_app.presentation.dialogs._base_dialog import _BaseDialog
from settlement_app.presentation.theme import COLOR
from settlement_app.presentation.widgets.buttons import make_button


class RunAllConfirmDialog(_BaseDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "전체 프로세스 실행 확인",
            "PostgreSQL 데이터 가져오기부터 결과 전송 전 단계까지 순차 실행합니다. "
            "PG 결제 포맷은 미정이므로 현재 프로토타입에서는 생략합니다.",
            parent,
            width=560,
        )

        steps_title = QLabel("실행 순서")
        steps_title.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{COLOR['text']};"
        )
        self.body.addWidget(steps_title)

        # TODO: RunAllUseCase.describe_steps()에서 단계 레이블을 가져와
        #       하드코딩 목록 대신 실제 실행 순서를 반영하도록 변경
        steps = [
            "1. 지사/도메인/ScraperHost 매핑 가져오기",
            "2. ScraperHost별 Playwright 스크립트 전달",
            "3. Excel 다운로드",
            "4. 정산 실행 및 검증",
            "5. 실패 항목만 검토",
            "6. 결과 내역에서 수동 전송",
        ]
        for s in steps:
            lbl = QLabel(s)
            lbl.setStyleSheet(f"font-size:12px; color:{COLOR['text_secondary']};")
            self.body.addWidget(lbl)

        cancel = make_button("취소", "secondary")
        run    = make_button("실행 시작", "primary")
        cancel.clicked.connect(self.reject)
        run.clicked.connect(self.accept)
        self.add_footer(cancel, run)
