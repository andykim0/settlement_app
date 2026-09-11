# -*- coding: utf-8 -*-
"""
모니터링 페이지 — 7개 중 5번째.

스크래퍼 실행 상태와 스트리밍 로그 출력을 실시간으로 표시.

레이아웃:
  - 실행 선택기 드롭다운 (전체 / run-id별)
  - 상태 패널: id, source, status, 시작 시각, 경과 시간, 출력 경로를 포함한
    알려진 실행 테이블
  - QPlainTextEdit 로그 표시 영역 (읽기 전용, 모노스페이스, 자동 스크롤)
  - 지우기 버튼
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from settlement_app.application.dto.run_state import RunState, RunStatus
from settlement_app.presentation.theme import COLOR
from settlement_app.presentation.widgets.buttons import make_button
from settlement_app.presentation.widgets.cards import Card
from settlement_app.presentation.widgets.pages._scaffold import page_header, page_scaffold

if TYPE_CHECKING:
    from settlement_app.application.services.run_registry import RunRegistry


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

_STATUS_COLOR: dict[str, str] = {
    RunStatus.QUEUED.value:    COLOR["neutral_fg"],
    RunStatus.RUNNING.value:   COLOR["info_fg"],
    RunStatus.SUCCEEDED.value: COLOR["success_fg"],
    RunStatus.FAILED.value:    COLOR["danger_fg"],
}


def _fmt_dt(dt: datetime.datetime | None) -> str:
    return dt.strftime("%H:%M:%S") if dt else "-"


def _fmt_elapsed(state: RunState) -> str:
    secs = state.runtime_seconds
    if secs is None:
        return "-"
    m, s = divmod(int(secs), 60)
    return f"{m}m {s}s" if m else f"{s}s"


# ---------------------------------------------------------------------------
# 실행 상태 행 위젯
# ---------------------------------------------------------------------------

_ERR_PREVIEW_MAX = 140


class _RunRow(QFrame):
    """RunState 하나에 대한 컴팩트 카드형 상태 표시.

    좁은 사이드바에서도 겹침 없이 들어가도록 2~3행 세로 레이아웃을 사용:
      1행: [소스 배지]  [상태]                       시각 · 경과
      2행: 출력 파일 / 에러 메시지 (있을 때만, 줄바꿈)
      3행: run_id (작고 흐리게)
    """

    def __init__(self, state: RunState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.run_id = state.run_id
        self.setFrameShape(QFrame.NoFrame)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 6, 0, 6)
        v.setSpacing(2)

        # --- 1행: 배지 + 상태 + 시각/경과 ---------------------------------
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        src_lbl = QLabel(state.source.upper())
        src_lbl.setAlignment(Qt.AlignCenter)
        src_lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        src_lbl.setStyleSheet(
            f"font-size:11px; font-weight:700; "
            f"background:{COLOR['primary_soft']}; "
            f"color:{COLOR['primary']}; "
            f"border-radius:4px; padding:2px 8px;"
        )
        top.addWidget(src_lbl)

        self._status_lbl = QLabel(state.status.value)
        self._status_lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        top.addWidget(self._status_lbl)

        top.addStretch(1)

        self._time_lbl = QLabel("")
        self._time_lbl.setStyleSheet(
            f"font-size:11px; color:{COLOR['text_secondary']};"
        )
        self._time_lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        top.addWidget(self._time_lbl)

        v.addLayout(top)

        # --- 2행: 출력/에러 메시지 (필요 시에만 표시) ----------------------
        self._output_lbl = QLabel("")
        self._output_lbl.setWordWrap(True)
        self._output_lbl.setStyleSheet(
            f"font-size:11px; color:{COLOR['text_muted']};"
        )
        self._output_lbl.hide()
        v.addWidget(self._output_lbl)

        # --- 3행: run_id (참고용, 흐리게) ---------------------------------
        id_lbl = QLabel(state.run_id)
        id_lbl.setStyleSheet(f"font-size:10px; color:{COLOR['text_muted']};")
        id_lbl.setToolTip(state.run_id)
        v.addWidget(id_lbl)

        self._refresh(state)

    def refresh(self, state: RunState) -> None:
        self._refresh(state)

    def _refresh(self, state: RunState) -> None:
        color = _STATUS_COLOR.get(state.status.value, COLOR["text_muted"])
        self._status_lbl.setText(state.status.value)
        self._status_lbl.setStyleSheet(
            f"font-size:11px; font-weight:600; color:{color};"
        )

        parts: list[str] = []
        if state.started_at:
            parts.append(_fmt_dt(state.started_at))
        elapsed = _fmt_elapsed(state)
        if elapsed != "-":
            parts.append(elapsed)
        self._time_lbl.setText(" · ".join(parts))

        if state.output_file_paths:
            self._output_lbl.setText(", ".join(state.output_file_paths))
            self._output_lbl.setToolTip("\n".join(state.output_file_paths))
            self._output_lbl.setStyleSheet(
                f"font-size:11px; color:{COLOR['text_muted']};"
            )
            self._output_lbl.show()
        elif state.error_message:
            preview = state.error_message.replace("\n", " ").strip()
            if len(preview) > _ERR_PREVIEW_MAX:
                preview = preview[: _ERR_PREVIEW_MAX - 1] + "…"
            self._output_lbl.setText(f"ERR: {preview}")
            self._output_lbl.setToolTip(state.error_message)
            self._output_lbl.setStyleSheet(
                f"font-size:11px; color:{COLOR['danger_fg']};"
            )
            self._output_lbl.show()
        else:
            self._output_lbl.clear()
            self._output_lbl.setToolTip("")
            self._output_lbl.hide()


# ---------------------------------------------------------------------------
# 페이지
# ---------------------------------------------------------------------------

class MonitoringPage(QWidget):
    back_requested = Signal()

    def __init__(
        self,
        registry: "RunRegistry",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        # run_id → _RunRow, 빠른 갱신용
        self._run_rows: dict[str, _RunRow] = {}
        # 현재 선택된 필터: None은 "전체 실행"을 의미
        self._filter_run_id: str | None = None

        page, box = page_scaffold()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        box.addWidget(page_header(
            "모니터링",
            "실행 중인 스크래퍼의 실시간 상태와 로그를 확인합니다",
        ))

        # --- Splitter: 상태 패널(왼쪽) + 로그 표시 영역(오른쪽) ---------------
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ---- 왼쪽: 실행 상태 패널 ------------------------------------------
        left_widget = QWidget()
        left_widget.setMinimumWidth(340)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        status_card = Card("실행 목록")
        self._back_btn = make_button("← 뒤로", "ghost")
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self.back_requested.emit)
        status_card.header.insertWidget(0, self._back_btn)
        self._run_list_layout = QVBoxLayout()
        self._run_list_layout.setSpacing(2)
        self._run_list_layout.setContentsMargins(0, 0, 0, 0)

        self._no_runs_lbl = QLabel("실행 이력 없음")
        self._no_runs_lbl.setStyleSheet(f"font-size:12px; color:{COLOR['text_muted']};")
        self._run_list_layout.addWidget(self._no_runs_lbl)

        status_card.body.addLayout(self._run_list_layout)
        left_layout.addWidget(status_card)
        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # ---- 오른쪽: 로그 표시 영역 ----------------------------------------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        log_card = Card("로그")

        # 셀렉터 행
        sel_row = QHBoxLayout()
        sel_row.setSpacing(8)
        sel_lbl = QLabel("실행 필터:")
        sel_lbl.setStyleSheet(f"font-size:12px; color:{COLOR['text_secondary']};")
        sel_row.addWidget(sel_lbl)
        self._run_selector = QComboBox()
        self._run_selector.addItem("전체 실행", None)
        self._run_selector.setMinimumWidth(200)
        self._run_selector.currentIndexChanged.connect(self._on_selector_changed)
        sel_row.addWidget(self._run_selector)
        sel_row.addStretch()
        clear_btn = make_button("지우기", "ghost")
        clear_btn.clicked.connect(self._on_clear)
        sel_row.addWidget(clear_btn)
        log_card.body.addLayout(sel_row)

        # 컬럼 헤더
        col_hdr = QLabel(
            "TIMESTAMP          SOURCE   STATUS    STEP / LOG LINE"
        )
        col_hdr.setStyleSheet(
            f"font-family: ui-monospace, Menlo, Consolas, monospace; "
            f"font-size:10px; color:{COLOR['text_muted']};"
        )
        log_card.body.addWidget(col_hdr)

        # 메인 로그 영역
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMinimumHeight(380)
        mono_font = QFont("ui-monospace, Menlo, Consolas, monospace")
        mono_font.setStyleHint(QFont.Monospace)
        mono_font.setPointSize(11)
        self._log_view.setFont(mono_font)
        self._log_view.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background: {COLOR['surface']};"
            f"  color: {COLOR['text_secondary']};"
            f"  border: 1px solid {COLOR['border']};"
            f"  border-radius: 6px;"
            f"  padding: 8px;"
            f"}}"
        )
        log_card.body.addWidget(self._log_view)

        right_layout.addWidget(log_card)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # splitter를 위젯으로 감싸서 페이지의 VBoxLayout에 추가 가능하게 함
        split_container = QWidget()
        split_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sc_layout = QHBoxLayout(split_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_layout.addWidget(splitter)
        box.addWidget(split_container, 1)

        # --- 레지스트리 시그널 구독 ------------------------------------
        registry.run_added.connect(self._on_run_added)
        registry.run_status_changed.connect(self._on_status_changed)
        registry.run_log_appended.connect(self._on_log_appended)

    # -----------------------------------------------------------------------
    # 레지스트리 시그널 슬롯 (메인 스레드에서 실행)
    # -----------------------------------------------------------------------

    def _on_run_added(self, run_id: str) -> None:
        """상태 패널과 선택기에 새 행 추가."""
        state = self._registry.get_run(run_id)
        if state is None:
            return

        # "실행 이력 없음" 플레이스홀더 제거
        if self._no_runs_lbl.isVisible():
            self._no_runs_lbl.hide()

        row = _RunRow(state)
        self._run_rows[run_id] = row
        self._run_list_layout.insertWidget(0, row)  # newest at top

        # 셀렉터에 추가
        label = f"{state.source.upper()} #{len(self._run_rows)}"
        self._run_selector.addItem(label, run_id)

    def _on_status_changed(self, run_id: str, status: str) -> None:
        state = self._registry.get_run(run_id)
        if state is None:
            return
        row = self._run_rows.get(run_id)
        if row is not None:
            row.refresh(state)

    def _on_log_appended(self, run_id: str, line: str) -> None:
        """선택기가 허용하는 경우 로그 뷰에 라인 추가."""
        if self._filter_run_id is not None and self._filter_run_id != run_id:
            return
        self._log_view.appendPlainText(line)
        # 맨 아래로 자동 스크롤
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # -----------------------------------------------------------------------
    # UI 핸들러
    # -----------------------------------------------------------------------

    def _on_selector_changed(self, index: int) -> None:
        run_id = self._run_selector.itemData(index)
        self._filter_run_id = run_id
        self._rebuild_log_for_filter()

    def _on_clear(self) -> None:
        self._log_view.clear()

    def _rebuild_log_for_filter(self) -> None:
        """필터 변경 시 레지스트리에서 로그 뷰를 재구성."""
        self._log_view.clear()
        if self._filter_run_id is None:
            # 전체 실행 표시
            for state in self._registry.list_runs():
                for line in state.last_log_lines:
                    self._log_view.appendPlainText(line)
        else:
            lines = self._registry.tail_logs(self._filter_run_id, n=200)
            for line in lines:
                self._log_view.appendPlainText(line)
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # -----------------------------------------------------------------------
    # 공개 API
    # -----------------------------------------------------------------------

    def filter_to_run(self, run_id: str) -> None:
        """
        선택기에서 특정 실행을 미리 선택.

        탐색 후 ExcelDownloadPage._on_view_logs()에서 호출됨.
        """
        for i in range(self._run_selector.count()):
            if self._run_selector.itemData(i) == run_id:
                self._run_selector.setCurrentIndex(i)
                return

    def set_back_enabled(self, enabled: bool) -> None:
        """페이지 내 뒤로 버튼을 MainWindow의 히스토리 상태와 동기화."""
        self._back_btn.setEnabled(enabled)
