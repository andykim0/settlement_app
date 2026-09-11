# -*- coding: utf-8 -*-
"""대시보드 페이지 — 7개 중 1번째."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from settlement_app.application.services.dashboard_service import DashboardService
from settlement_app.application.services.run_registry import RunRegistry
from settlement_app.presentation.dialogs.run_all_confirm import RunAllConfirmDialog
from settlement_app.presentation.widgets.badge import badge_cell
from settlement_app.presentation.widgets.buttons import make_button
from settlement_app.presentation.widgets.cards import Card, StatCard
from settlement_app.presentation.widgets.table import FlatTable
from settlement_app.presentation.widgets.pages._scaffold import page_header, page_scaffold


class DashboardPage(QWidget):
    def __init__(
        self,
        service: DashboardService,
        registry: RunRegistry,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._registry = registry

        page, box = page_scaffold()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        run_all = make_button("전체 프로세스 실행", "primary")
        run_all.clicked.connect(lambda: RunAllConfirmDialog(self).exec())
        box.addWidget(page_header(
            "대시보드",
            "전체 정산 프로세스와 최근 작업/오류를 한 곳에서 확인합니다",
            run_all,
        ))

        stats = service.get_stats()

        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        stats_row.addWidget(StatCard(
            "오늘 대상 지사",
            f"{stats.branch_count}개",
            "PostgreSQL 동기화 완료",
            "muted",
        ))
        stats_row.addWidget(StatCard(
            "Excel Download",
            f"{stats.excel_done} / {stats.excel_total}",
            f"실행 중 {stats.excel_running} · 에러 {stats.excel_error}",
            "info",
        ))
        stats_row.addWidget(StatCard(
            "정산 검증",
            f"{stats.settlement_done} / {stats.settlement_total}",
            f"검증 실패 {stats.settlement_fail}건",
            "error",
        ))
        stats_row.addWidget(StatCard(
            "전송 대기",
            f"{stats.send_pending}건",
            "DynamoDB · S3 · NAS",
            "muted",
        ))
        box.addLayout(stats_row)

        tbl_row = QHBoxLayout()
        tbl_row.setSpacing(16)

        recent = Card("최근 작업")
        self._activity_table = FlatTable(["시간", "단계", "대상", "상태"])
        self._activity_table.setMinimumHeight(220)
        recent.body.addWidget(self._activity_table)
        tbl_row.addWidget(recent, 1)

        errors = Card("최근 에러")
        self._error_table = FlatTable(["시간", "ScraperHost", "지사/도메인", "오류"])
        self._error_table.setMinimumHeight(220)
        errors.body.addWidget(self._error_table)
        tbl_row.addWidget(errors, 1)

        box.addLayout(tbl_row)
        box.addStretch()

        # 초기 채우기 + 실시간 업데이트 구독
        self._refresh_activity_table()
        self._refresh_error_table()
        registry.run_added.connect(self._on_run_changed)
        registry.run_status_changed.connect(self._on_run_changed)

    # -----------------------------------------------------------------------
    # 갱신
    # -----------------------------------------------------------------------

    def _refresh_activity_table(self) -> None:
        self._activity_table.clear_rows()
        for row in self._service.get_recent_activities():
            self._activity_table.add_row([
                row.time,
                row.step,
                row.target,
                badge_cell(row.status_label, row.status),
            ])

    def _refresh_error_table(self) -> None:
        self._error_table.clear_rows()
        for row in self._service.get_recent_errors():
            self._error_table.add_row([
                row.time,
                row.scraper_host_id,
                row.branch_domain,
                row.message,
            ])

    def _on_run_changed(self, *_args) -> None:
        # 시그널은 (run_id) 또는 (run_id, status)를 전달; 무엇이든 상관없이 —
        # 현재 레지스트리 상태로 두 테이블을 재구성.
        self._refresh_activity_table()
        self._refresh_error_table()
