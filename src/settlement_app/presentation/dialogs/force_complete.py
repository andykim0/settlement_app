# -*- coding: utf-8 -*-
"""ForceCompleteDialog — 작업 상태 강제 완료 다이얼로그."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QWidget

from settlement_app.presentation.dialogs._base_dialog import _BaseDialog
from settlement_app.presentation.widgets.badge import badge_cell
from settlement_app.presentation.widgets.buttons import make_button
from settlement_app.presentation.widgets.table import FlatTable


class ForceCompleteDialog(_BaseDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "작업 상태 강제 완료",
            "[에러] 또는 [대기] 상태의 Excel Download 작업만 강제로 실행완료 "
            "처리합니다. [실행 중]은 대상에서 제외됩니다.",
            parent,
            width=560,
        )

        # TODO: DownloadJobRepository.get_forceable_jobs(selected_ids)로 채우기
        t = FlatTable(["대상", "현재 상태", "처리 후"])
        t.setMinimumHeight(120)
        t.add_row(["guro_03 / baemin",   badge_cell("에러",  "danger"),  badge_cell("실행완료", "success")])
        t.add_row(["seocho_05 / coupang", badge_cell("대기", "neutral"), badge_cell("실행완료", "success")])
        self.body.addWidget(t)

        row = QHBoxLayout()
        lbl = QLabel("사유")
        lbl.setObjectName("fieldLabel")
        lbl.setFixedWidth(40)
        self.reason = QPlainTextEdit("테스트 검증용 수동 완료")
        self.reason.setFixedHeight(36)
        row.addWidget(lbl)
        row.addWidget(self.reason, 1)
        self.body.addLayout(row)

        cancel = make_button("취소", "secondary")
        ok     = make_button("완료 처리", "primary")
        cancel.clicked.connect(self.reject)
        # TODO: 수락 시 ForceCompleteUseCase.execute(job_ids, reason=self.reason.toPlainText()) 호출
        ok.clicked.connect(self.accept)
        self.add_footer(cancel, ok)
