# -*- coding: utf-8 -*-
"""결과 내역 페이지 — 7개 중 6번째."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from settlement_app.presentation.dialogs.send_complete import SendAllOverlay
from settlement_app.presentation.widgets.badge import badge_cell
from settlement_app.presentation.widgets.buttons import make_button, row_buttons
from settlement_app.presentation.widgets.cards import Card, StatCard
from settlement_app.presentation.widgets.table import FlatTable
from settlement_app.presentation.widgets.pages._scaffold import page_header, page_scaffold
from settlement_app.presentation.theme import COLOR

if TYPE_CHECKING:
    from settlement_app.application.services.results_service import ResultsService


class ResultsPage(QWidget):
    def __init__(
        self,
        results_service: "ResultsService",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._results_service = results_service

        page, box = page_scaffold()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        # TODO: wire "전체 전송" to ResultsService.enqueue_send_all()
        #       — must launch in background; show SendAllOverlay as progress indicator
        send_all = make_button("전체 전송", "primary")
        send_all.clicked.connect(lambda: SendAllOverlay(self).exec())
        box.addWidget(page_header(
            "결과 내역",
            "정산 실행 후 산출 결과와 전송 상태를 확인합니다",
            send_all,
        ))

        # --- KPI row ----------------------------------------------------
        # TODO: replace with ResultsSummaryDTO from ResultsService.get_summary()
        stats = QHBoxLayout()
        stats.setSpacing(16)
        stats.addWidget(StatCard("정산 완료",   "14 / 16",
                                 "전송 가능 12건", "ok"))
        stats.addWidget(StatCard("검증 실패",   "2건",
                                 "실패 항목만 표시", "muted"))
        stats.addWidget(StatCard("S3/NAS 파일", "28개",
                                 "Raw + Result Excel", "info"))
        stats.addWidget(StatCard("DynamoDB DAILY", "1,284건",
                                 "settlement_ledger", "muted"))
        box.addLayout(stats)

        # --- Results list -----------------------------------------------
        # NOTE: "정산액" column shows raw integer strings — money display formatting
        #       (comma separators, currency symbol) belongs in a shared formatter util,
        #       NOT in the page.  Money calculation logic → settlement-logic-specialist.
        rl = Card("지사별 결과 리스트")
        t = FlatTable(["상태", "지사", "도메인", "정산액", "검증", "Excel",
                       "DynamoDB", "S3/NAS", "작업"])
        t.setMinimumHeight(280)

        branch_rows = results_service.list_branch_results()
        if branch_rows:
            for row in branch_rows:
                t.add_row([
                    badge_cell(row.row_status_label, row.row_status),
                    row.branch_code,
                    row.domain,
                    row.total_payout_display,      # settlement-logic-specialist가 채울 예정
                    badge_cell(row.verification_label, row.verification_status),
                    row.excel_files,
                    row.dynamodb_items,            # settlement-logic-specialist가 채울 예정
                    row.send_status,               # settlement-logic-specialist가 채울 예정
                    row_buttons(("상세", "ghost")),
                ])
        else:
            # 실행된 스크래퍼가 없을 때 빈 상태 행 표시
            t.add_row(["아직 실행된 스크래퍼가 없습니다.", "", "", "", "", "", "", "", ""])

        rl.body.addWidget(t)
        box.addWidget(rl)

        # --- Transfer targets description --------------------------------
        targets = Card("전송 대상")
        row = QHBoxLayout()
        row.setSpacing(50)
        l1 = QLabel("DynamoDB: settlement_ledger DAILY / VERIFY / FILE")
        l2 = QLabel("S3: Raw / Curated / Archive · NAS: 날짜/지사/도메인/파일명.xlsx")
        for lbl in (l1, l2):
            lbl.setStyleSheet(f"font-size:12px; font-weight:600; color:{COLOR['text']};")
            row.addWidget(lbl)
        row.addStretch()
        targets.body.addLayout(row)
        box.addWidget(targets)
        box.addStretch()
