# -*- coding: utf-8 -*-
"""
엑셀 다운로드 페이지 — 7개 중 3번째.

실시간 상태를 표시하는 두 개의 워커 카드(Coupang / Baemin) 표시.
RunRegistry 시그널을 구독하고 상태 변경 시 카드를 갱신.

TODO: 현재 Coupang 워커 하나와 Baemin 워커 하나로 하드코딩되어 있으며,
      설정에 따라 동적 워커 수를 지원해야 함.
"""
from __future__ import annotations

import datetime
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QDate, QThreadPool, Qt, Signal
from PySide6.QtWidgets import (
    QDateEdit, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from settlement_app.application.dto.run_state import RunState, RunStatus
from settlement_app.presentation.theme import COLOR
from settlement_app.presentation.widgets.badge import Badge
from settlement_app.presentation.widgets.buttons import make_button
from settlement_app.presentation.widgets.cards import Card
from settlement_app.presentation.widgets.pages._scaffold import page_header, page_scaffold

if TYPE_CHECKING:
    from settlement_app.application.services.run_registry import RunRegistry
    from settlement_app.infrastructure.settings.app_settings import AppSettings


# ---------------------------------------------------------------------------
# ScraperHost 카드 위젯
# ---------------------------------------------------------------------------

_STATUS_COLOR: dict[str, str] = {
    RunStatus.QUEUED.value:    COLOR["neutral_fg"],
    RunStatus.RUNNING.value:   COLOR["info_fg"],
    RunStatus.SUCCEEDED.value: COLOR["success_fg"],
    RunStatus.FAILED.value:    COLOR["danger_fg"],
    "idle":                    COLOR["text_muted"],
}

_STATUS_LABEL: dict[str, str] = {
    RunStatus.QUEUED.value:    "대기",
    RunStatus.RUNNING.value:   "실행 중",
    RunStatus.SUCCEEDED.value: "완료",
    RunStatus.FAILED.value:    "에러",
    "idle":                    "대기 없음",
}


class _WorkerCard(QFrame):
    """
    하나의 스크래퍼 소스(Coupang 또는 Baemin)에 대한 소형 상태 카드.

    카드는 순수 표시 위젯. ExcelDownloadPage가 시그널 연결을 소유하고
    update_run()을 호출.
    """

    def __init__(
        self,
        source: str,
        on_run: object,
        on_view_logs: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.source = source
        self.setObjectName("card")
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(8)

        # 헤더 행: 소스명 + 실행 버튼
        header = QHBoxLayout()
        title = QLabel(source.upper())
        title.setObjectName("cardTitle")
        header.addWidget(title)
        header.addStretch()
        self._run_btn = make_button("실행", "primary")
        self._run_btn.clicked.connect(on_run)
        header.addWidget(self._run_btn)
        v.addLayout(header)

        # 상태 행
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._status_lbl = QLabel("대기 없음")
        self._status_lbl.setStyleSheet(
            f"font-size:12px; font-weight:600; color:{COLOR['text_muted']};"
        )
        status_row.addWidget(self._status_lbl)
        status_row.addStretch()
        self._ts_lbl = QLabel("")
        self._ts_lbl.setStyleSheet(f"font-size:11px; color:{COLOR['text_muted']};")
        status_row.addWidget(self._ts_lbl)
        v.addLayout(status_row)

        # 진행 상황 / 단계 레이블
        self._step_lbl = QLabel("")
        self._step_lbl.setStyleSheet(
            f"font-size:11px; color:{COLOR['text_secondary']};"
        )
        v.addWidget(self._step_lbl)

        # 출력 파일 경로 — 성공 후 표시
        self._output_lbl = QLabel("")
        self._output_lbl.setWordWrap(True)
        self._output_lbl.setStyleSheet(
            f"font-size:11px; color:{COLOR['text_muted']};"
        )
        self._output_lbl.hide()
        v.addWidget(self._output_lbl)

        # 오류 메시지 — 실패 후 표시
        self._error_lbl = QLabel("")
        self._error_lbl.setWordWrap(True)
        self._error_lbl.setStyleSheet(
            f"font-size:11px; color:{COLOR['danger_fg']};"
        )
        self._error_lbl.hide()
        v.addWidget(self._error_lbl)

        # 푸터: 로그 보기 버튼
        footer = QHBoxLayout()
        footer.addStretch()
        self._logs_btn = make_button("로그 보기", "ghost")
        self._logs_btn.clicked.connect(on_view_logs)
        footer.addWidget(self._logs_btn)
        v.addLayout(footer)

    def update_run(self, state: RunState) -> None:
        """RunState 스냅샷으로부터 카드를 갱신."""
        status_val = state.status.value
        color = _STATUS_COLOR.get(status_val, COLOR["text_muted"])
        label = _STATUS_LABEL.get(status_val, status_val)

        self._status_lbl.setText(label)
        self._status_lbl.setStyleSheet(
            f"font-size:12px; font-weight:600; color:{color};"
        )

        # 타임스탬프
        ts = state.finished_at or state.started_at
        if ts:
            self._ts_lbl.setText(ts.strftime("%H:%M:%S"))
        else:
            self._ts_lbl.setText("")

        # 단계 / 진행률
        if state.progress_step:
            self._step_lbl.setText(
                f"{state.progress_step}  {state.progress_pct}%"
            )
        else:
            self._step_lbl.setText("")

        # 출력 파일
        if state.output_file_paths:
            self._output_lbl.setText(
                "저장: " + ", ".join(state.output_file_paths)
            )
            self._output_lbl.show()
        else:
            self._output_lbl.hide()

        # 오류
        if state.error_message:
            self._error_lbl.setText(f"오류: {state.error_message}")
            self._error_lbl.show()
        else:
            self._error_lbl.hide()

        # 실행 중에는 실행 버튼 비활성화
        self._run_btn.setEnabled(state.status not in (RunStatus.RUNNING, RunStatus.QUEUED))


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

class ExcelDownloadPage(QWidget):
    view_logs_requested = Signal(str)  # run_id (아직 실행이 없으면 "")

    def __init__(
        self,
        registry: "RunRegistry",
        settings: "AppSettings | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        self._settings = settings

        # 소스별 가장 최근 run_id (첫 실행 전은 None)
        self._last_run_id: dict[str, str | None] = {
            "coupang": None,
            "baemin": None,
        }

        page, box = page_scaffold()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        # --- 페이지 헤더 -------------------------------------------------------
        run_all_btn = make_button("전체 실행", "primary")
        run_all_btn.clicked.connect(self._on_run_all)
        box.addWidget(page_header(
            "엑셀파일 다운로드",
            "Playwright 스크립트로 전일 정산 Excel 파일을 다운로드합니다",
            run_all_btn,
        ))

        # --- 실행 조건 카드 -----------------------------------------------
        cond = Card("실행 조건")
        cond_row = QHBoxLayout()
        cond_row.setSpacing(28)

        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        self._date_edit = QDateEdit(QDate(yesterday.year, yesterday.month, yesterday.day))
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        self._date_edit.setFixedWidth(170)
        cond_row.addWidget(_field("대상 날짜", self._date_edit))

        default_dir = (
            str(settings.storage.local_excel_dir)
            if settings and settings.storage.local_excel_dir
            else os.path.expanduser("~/Downloads/settlement_excels")
        )
        self._dir_edit = QLineEdit(default_dir)
        self._dir_edit.setMinimumWidth(320)
        cond_row.addWidget(_field("저장 디렉토리", self._dir_edit))

        scripts_row = QHBoxLayout()
        scripts_row.setSpacing(6)
        scripts_row.addWidget(Badge("baemin", "success"))
        scripts_row.addWidget(Badge("coupang", "success"))
        scripts_row.addStretch()
        scripts_w = QWidget()
        scripts_w.setLayout(scripts_row)
        scripts_w.setStyleSheet("background: transparent;")
        cond_row.addWidget(_field("도메인", scripts_w))

        cond_row.addStretch()
        cond.body.addLayout(cond_row)
        box.addWidget(cond)

        # --- ScraperHost 카드 -------------------------------------------------------
        workers_card = Card("ScraperHost 실행 상태")
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        self._coupang_card = _WorkerCard(
            "coupang",
            on_run=lambda: self._on_run_source("coupang"),
            on_view_logs=lambda: self._on_view_logs("coupang"),
        )
        self._baemin_card = _WorkerCard(
            "baemin",
            on_run=lambda: self._on_run_source("baemin"),
            on_view_logs=lambda: self._on_view_logs("baemin"),
        )
        cards_row.addWidget(self._coupang_card)
        cards_row.addWidget(self._baemin_card)
        cards_row.addStretch()
        workers_card.body.addLayout(cards_row)
        box.addWidget(workers_card)
        box.addStretch()

        # --- 레지스트리 시그널 구독 -------------------------------------
        registry.run_status_changed.connect(self._on_status_changed)
        registry.run_progress_updated.connect(self._on_progress_updated)

    # -----------------------------------------------------------------------
    # 버튼 핸들러
    # -----------------------------------------------------------------------

    def _on_run_all(self) -> None:
        self._on_run_source("coupang")
        self._on_run_source("baemin")

    def _on_run_source(self, source: str) -> None:
        """자격증명 검증 후 실행을 등록하고 워커를 제출."""
        missing = _check_credentials(source)
        if missing:
            QMessageBox.warning(
                self,
                "비밀번호 미설정",
                f"'{missing}' 가 설정되지 않았습니다.\n\n"
                f"키체인에 저장 (권장, 한 번만):\n"
                f'  python3 -c "import keyring; keyring.set_password('
                f"'settlement_app', '{missing}', '비밀번호')\"\n\n"
                f"또는 환경 변수로 임시 설정:\n"
                f"  export {missing}='비밀번호'",
            )
            return

        target_date = self._date_edit.date().toPython()
        output_dir = self._dir_edit.text().strip() or os.path.expanduser(
            "~/Downloads/settlement_excels"
        )

        # 모듈 로드 시 순환 임포트 방지를 위해 지연 임포트
        from settlement_app.infrastructure.scrapers.coupang_scraper import CoupangScraper
        from settlement_app.infrastructure.scrapers.baemin_scraper import BaeminScraper
        from settlement_app.infrastructure.settings.app_settings import load_settings
        from settlement_app.workers.scraper_worker import make_worker

        settings = self._settings or load_settings()
        # 설정에서 활성 지사 코드를 읽어 레지스트리 및 워커에 전달
        active_branch_code = settings.scrapers.active_branch_code

        # 워커 시작 전에 레지스트리에 새 실행(QUEUED) 등록
        state = self._registry.register_run(source=source, branch_code=active_branch_code)
        self._last_run_id[source] = state.run_id

        scraper = (
            CoupangScraper(settings) if source == "coupang" else BaeminScraper(settings)
        )

        worker = make_worker(
            run_state=state,
            scraper=scraper,
            registry=self._registry,
            output_dir=output_dir,
            target_date=target_date,
            branch_code=active_branch_code,
        )
        QThreadPool.globalInstance().start(worker)

    def _on_view_logs(self, source: str) -> None:
        """MainWindow에 탐색 요청을 방출하고 해당 소스의 마지막 실행으로 모니터링을 필터링."""
        run_id = self._last_run_id.get(source) or ""
        self.view_logs_requested.emit(run_id)

    # -----------------------------------------------------------------------
    # 레지스트리 시그널 슬롯
    # -----------------------------------------------------------------------

    def _on_status_changed(self, run_id: str, status: str) -> None:
        self._refresh_card_for_run(run_id)

    def _on_progress_updated(self, run_id: str, step: str, pct: int) -> None:
        self._refresh_card_for_run(run_id)

    def _refresh_card_for_run(self, run_id: str) -> None:
        state = self._registry.get_run(run_id)
        if state is None:
            return
        card = self._card_for_source(state.source)
        if card is not None:
            card.update_run(state)

    def _card_for_source(self, source: str) -> "_WorkerCard | None":
        if source == "coupang":
            return self._coupang_card
        if source == "baemin":
            return self._baemin_card
        return None


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _field(label_text: str, value_widget: QWidget) -> QWidget:
    col = QVBoxLayout()
    col.setSpacing(4)
    lbl = QLabel(label_text)
    lbl.setObjectName("fieldLabel")
    col.addWidget(lbl)
    col.addWidget(value_widget)
    wrap = QWidget()
    wrap.setLayout(col)
    wrap.setStyleSheet("background: transparent;")
    return wrap


_REQUIRED_ENV: dict[str, str] = {
    "coupang": "COUPANG_PW",
    "baemin":  "BAEMIN_PASSWORD",
}


def _check_credentials(source: str) -> str | None:
    """누락된 자격증명 이름을 반환, 사용 가능하면 None 반환.

    OS 키체인을 먼저 조회(권장)한 뒤 환경변수로 폴백.
    coupang_scraper._get_coupang_pw 및 baemin_scraper._get_baemin_pw의
    조회 순서를 그대로 반영.
    """
    var = _REQUIRED_ENV.get(source)
    if not var:
        return None
    try:
        import keyring
        if keyring.get_password("settlement_app", var):
            return None
    except Exception:
        pass  # keyring 백엔드 사용 불가 — 환경변수 확인으로 이동
    if os.environ.get(var):
        return None
    return var
