# -*- coding: utf-8 -*-
"""정산 실행 페이지 — 7개 중 4번째."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QVBoxLayout, QWidget

from settlement_app.presentation.dialogs.rider_mapping import RiderMappingDialog
from settlement_app.presentation.dialogs.settlement_mapping import SettlementMappingDialog
from settlement_app.presentation.widgets.badge import badge_cell
from settlement_app.presentation.widgets.buttons import make_button, row_buttons
from settlement_app.presentation.widgets.cards import Card
from settlement_app.presentation.widgets.table import FlatTable
from settlement_app.presentation.widgets.pages._scaffold import page_header, page_scaffold

if TYPE_CHECKING:
    from settlement_app.application.services.results_service import ResultsService


class SettlementRunPage(QWidget):
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

        # TODO: wire "전체 정산 실행" to SettlementRunUseCase.enqueue_all()
        #       — must NOT block the event loop; enqueue a job and return immediately
        run_all = make_button("전체 정산 실행", "primary")
        map_all = make_button("전체 라이더 매핑", "secondary")
        map_all.clicked.connect(lambda: RiderMappingDialog(self).exec())
        box.addWidget(page_header(
            "정산 실행",
            "다운로드된 Excel 파일을 기준으로 지사별 정산 계산, 라이더 매핑, "
            "결과 매핑을 수행합니다",
            run_all, map_all,
        ))

        # --- target list ------------------------------------------------
        tgt = Card("정산 대상")
        t = FlatTable(["상태", "지사 코드", "Excel 파일", "라이더 매핑",
                       "정산 상태", "검증", "DynamoDB 항목", "작업"])
        t.setMinimumHeight(240)

        # 컬럼 크기 고정: 작업 컬럼은 버튼 공간 확보 필요,
        # badge 컬럼(상태, 검증)은 badge_cell 내부 addStretch()가
        # ResizeToContents를 과소 보고하므로 고정폭 필요.
        # Excel 파일 컬럼이 나머지 공간을 채움.
        header = t.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)              # 상태 (badge)
        t.setColumnWidth(0, 95)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)   # 지사 코드
        header.setSectionResizeMode(2, QHeaderView.Stretch)            # Excel 파일
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # 라이더 매핑
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)   # 정산 상태
        header.setSectionResizeMode(5, QHeaderView.Fixed)              # 검증 (badge)
        t.setColumnWidth(5, 80)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)   # DynamoDB 항목
        header.setSectionResizeMode(7, QHeaderView.Fixed)              # 작업
        t.setColumnWidth(7, 300)
        t.verticalHeader().setDefaultSectionSize(56)

        target_rows = results_service.list_settlement_targets()
        if target_rows:
            for row in target_rows:
                t.add_row([
                    badge_cell(row.run_status_label, row.run_status),
                    row.branch_code,
                    row.excel_path,
                    "-",           # 라이더 수는 Excel 파싱 후 확인 — settlement-logic-specialist 담당
                    row.calc_status,
                    badge_cell(row.verification_label, row.verification_status),
                    "-",           # DynamoDB 항목 수는 정산 완료 후 채워짐 — 플레이스홀더
                    row_buttons(("정산", "ghost"), ("라이더 매핑", "ghost"),
                                ("정산 데이터 매핑", "ghost")),
                ])
        else:
            # 정산 대기 중인 스크래퍼 실행이 없을 때 빈 상태 행 표시
            t.add_row(["아직 실행된 스크래퍼가 없습니다.", "", "", "", "", "", "", ""])

        tgt.body.addWidget(t)

        # NOTE: cellClicked는 7번 컬럼의 모든 클릭에 반응 — 프로토타입 단축 구현.
        #       실제 구현 시 행별 "정산 데이터 매핑" 버튼 시그널을 개별 연결해야 함.
        t.cellClicked.connect(
            lambda row, col: SettlementMappingDialog(self).exec() if col == 7 else None
        )
        box.addWidget(tgt)

        # --- validation failures ----------------------------------------
        # TODO: populate from SettlementRunService.get_validation_failures()
        # TODO: financial columns (net_amount, lease_fee, withholding_tax) represent
        #       MONEY — hand off calculation/validation logic to settlement-logic-specialist
        # 아래 행은 플레이스홀더 예시이며, settlement-logic-specialist가
        # 검증 로직을 구현하면 실제 데이터로 교체 예정.
        fail = Card("검증 실패")
        f = FlatTable(["지사", "라이더", "항목", "차이"])
        f.setMinimumHeight(160)
        f.add_row(["guro_03",    "RIDER-1182", "net_amount",     "-3,200"])
        f.add_row(["guro_03",    "RIDER-2219", "lease_fee",      "+5,000"])
        f.add_row(["yeouido_01", "RIDER-0091", "withholding_tax", "-410"])
        fail.body.addWidget(f)
        fail.setMaximumWidth(560)

        bottom = QHBoxLayout()
        bottom.addWidget(fail)
        bottom.addStretch()
        box.addLayout(bottom)
        box.addStretch()
