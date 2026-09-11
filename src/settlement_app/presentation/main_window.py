# -*- coding: utf-8 -*-
"""MainWindow — 쉘, 헤더, 사이드바, 스택 페이지."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from settlement_app.application.services.dashboard_service import DashboardService
from settlement_app.application.services.results_service import ResultsService
from settlement_app.application.services.run_registry import RunRegistry
from settlement_app.infrastructure.settings.app_settings import load_settings
from settlement_app.presentation.theme import COLOR
from settlement_app.presentation.widgets.pages.dashboard_page import DashboardPage
from settlement_app.presentation.widgets.pages.data_import_page import DataImportPage
from settlement_app.presentation.widgets.pages.excel_download_page import ExcelDownloadPage
from settlement_app.presentation.widgets.pages.settlement_run_page import SettlementRunPage
from settlement_app.presentation.widgets.pages.monitoring_page import MonitoringPage
from settlement_app.presentation.widgets.pages.results_page import ResultsPage
from settlement_app.presentation.widgets.pages.settings_page import SettingsPage

_NAV_ITEMS: list[tuple[str, str]] = [
    ("☰",  "대시보드"),
    ("\U0001F4D6", "데이터 가져오기"),
    ("\U0001F4C4", "엑셀 다운로드"),
    ("\U0001F4DD", "정산 실행"),
    ("\U0001F4C8", "모니터링"),
    ("\U0001F4E4", "결과 내역"),
    ("⚙",  "설정"),
]


class _Header(QFrame):
    def __init__(
        self,
        on_back: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("header")
        self.setFixedHeight(56)
        h = QHBoxLayout(self)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(10)

        self._back_btn = QPushButton("←")
        self._back_btn.setObjectName("headerBackBtn")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setFixedSize(32, 28)
        self._back_btn.setToolTip("이전 화면")
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(lambda _=False: on_back())
        h.addWidget(self._back_btn)

        logo = QLabel("P")
        logo.setObjectName("logoBox")
        logo.setFixedSize(28, 28)
        h.addWidget(logo)

        title = QLabel("배달 정산 로컬 관리자")
        title.setObjectName("appTitle")
        h.addWidget(title)
        h.addStretch()

    def set_back_enabled(self, enabled: bool) -> None:
        self._back_btn.setEnabled(enabled)


class _SideNav(QFrame):
    def __init__(self, on_change: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 18, 12, 18)
        v.setSpacing(2)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for idx, (glyph, label) in enumerate(_NAV_ITEMS):
            btn = QPushButton(f"  {glyph}   {label}")
            btn.setObjectName("navItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda _=False, i=idx: on_change(i))
            self._group.addButton(btn, idx)
            v.addWidget(btn)

        v.addStretch()

    def select(self, idx: int) -> None:
        btn = self._group.button(idx)
        if btn:
            btn.setChecked(True)


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("배달 정산 로컬 관리자")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)

        self._history: list[int] = []

        root = QWidget()
        root.setObjectName("root")
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._header = _Header(on_back=self._on_back)
        v.addWidget(self._header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.nav = _SideNav(self._on_nav)
        body.addWidget(self.nav)

        # 단일 공유 레지스트리 — ExcelDownloadPage와 MonitoringPage 모두
        # 이 시그널을 구독한다. 메인 스레드에서 생성해야 Qt가 워커의
        # 시그널 emit을 메인 스레드로 마샬링한다.
        self._run_registry = RunRegistry(parent=self)

        self.stack = QStackedWidget()
        # NOTE: 페이지 순서는 _NAV_ITEMS 인덱스와 동기화 유지 필요
        self._app_settings = load_settings()
        dashboard_service = DashboardService(registry=self._run_registry)
        results_service = ResultsService(registry=self._run_registry)
        excel_page = ExcelDownloadPage(
            registry=self._run_registry,
            settings=self._app_settings,
        )
        self._monitoring_page = MonitoringPage(registry=self._run_registry)
        self._monitoring_page.back_requested.connect(self._on_back)
        excel_page.view_logs_requested.connect(self._on_view_logs_requested)
        self._pages: list[QWidget] = [
            DashboardPage(service=dashboard_service, registry=self._run_registry),
            DataImportPage(settings=self._app_settings),
            excel_page,
            SettlementRunPage(results_service=results_service),
            self._monitoring_page,
            ResultsPage(results_service=results_service),
            SettingsPage(settings=self._app_settings),
        ]

        for page in self._pages:
            scroll = QScrollArea()
            scroll.setWidget(page)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setStyleSheet(f"QScrollArea {{ background: {COLOR['bg']}; }}")
            self.stack.addWidget(scroll)

        body.addWidget(self.stack, 1)
        v.addLayout(body, 1)
        self.setCentralWidget(root)

        self.nav.select(0)
        self.stack.setCurrentIndex(0)

    def _on_nav(self, idx: int) -> None:
        self._navigate(idx, record_history=True)

    def _on_back(self) -> None:
        if not self._history:
            return
        prev = self._history.pop()
        self._navigate(prev, record_history=False)

    def _on_view_logs_requested(self, run_id: str) -> None:
        self._navigate(4, record_history=True)  # 4 = 모니터링
        if run_id:
            self._monitoring_page.filter_to_run(run_id)

    def _navigate(self, idx: int, *, record_history: bool) -> None:
        current = self.stack.currentIndex()
        if current == idx:
            return
        if record_history:
            self._history.append(current)
        self.stack.setCurrentIndex(idx)
        self.nav.select(idx)
        has_history = bool(self._history)
        self._header.set_back_enabled(has_history)
        self._monitoring_page.set_back_enabled(has_history)
