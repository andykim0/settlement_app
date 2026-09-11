# -*- coding: utf-8 -*-
"""SettlementMappingDialog — 정산 데이터 매핑."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from settlement_app.presentation.dialogs._base_dialog import _BaseDialog
from settlement_app.presentation.widgets.badge import badge_cell
from settlement_app.presentation.widgets.buttons import make_button
from settlement_app.presentation.widgets.table import FlatTable


class SettlementMappingDialog(_BaseDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "정산 데이터 매핑",
            "기본 납부 내역, 지사 공통 납부, 라이더 개별 납부를 포함해 "
            "Python 산출 결과와 Excel 산식 결과를 비교합니다.",
            parent,
            width=720,
        )

        # TODO: SettlementVerificationService.get_mapping_rows(branch_id, run_id)로 채우기
        # NOTE: "기본 지급", "공통 납부", "개별 납부", "Net" 컬럼은 금액 필드 —
        #       계산 로직은 settlement-logic-specialist 담당이며 이 레이어가 아님.
        #       이 다이얼로그는 사전 계산된 SettlementMappingRowDTO 값만 표시해야 함.
        t = FlatTable(["라이더", "기본 지급", "공통 납부", "개별 납부", "Net", "검증"])
        t.setMinimumHeight(160)
        t.add_row(["RIDER-1001", "128,000", "8,300", "0",     "119,700", badge_cell("성공", "success")])
        t.add_row(["RIDER-1182", "104,000", "8,300", "3,200", "92,500",  badge_cell("실패", "danger")])
        t.add_row(["RIDER-2219", "96,000",  "8,300", "5,000", "82,700",  badge_cell("실패", "danger")])
        self.body.addWidget(t)

        note = QLabel("실패한 항목만 검증 패널과 결과 내역에 노출됩니다.")
        note.setObjectName("errorNote")
        self.body.addWidget(note)

        close = make_button("닫기", "secondary")
        close.clicked.connect(self.accept)
        self.add_footer(close)
