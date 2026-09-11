# -*- coding: utf-8 -*-
"""RiderMappingDialog — 라이더 매핑."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from settlement_app.presentation.dialogs._base_dialog import _BaseDialog
from settlement_app.presentation.widgets.badge import badge_cell
from settlement_app.presentation.widgets.buttons import make_button
from settlement_app.presentation.widgets.table import FlatTable


class RiderMappingDialog(_BaseDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "라이더 매핑",
            "Excel 데이터에 있는 라이더와 PostgreSQL 등록 라이더를 비교하고, "
            "미등록 라이더는 지사 소속으로 업데이트합니다.",
            parent,
            width=640,
        )

        # TODO: 정적 행 대신 RiderMappingService.compare_excel_to_db(branch_id, excel_path)로 채우기
        t = FlatTable(["Excel 라이더", "PostgreSQL", "처리"])
        t.setMinimumHeight(170)
        t.add_row(["김현우 / 010-1111", "RIDER-1001", badge_cell("일치",        "success")])
        t.add_row(["박서준 / 010-2222", "미등록",     badge_cell("소속 업데이트", "warning")])
        t.add_row(["이도윤 / 010-3333", "RIDER-1028", badge_cell("일치",        "success")])
        self.body.addWidget(t)

        # TODO: RiderMappingService.apply_updates(branch_id, mapping_result)에 연결
        run = make_button("PostgreSQL 업데이트", "primary")
        run.clicked.connect(self.accept)
        self.add_footer(run)
