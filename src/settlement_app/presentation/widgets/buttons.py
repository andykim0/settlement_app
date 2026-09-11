# -*- coding: utf-8 -*-
"""버튼 팩토리 헬퍼."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

_KIND_TO_OBJECT: dict[str, str] = {
    "primary":   "btnPrimary",
    "secondary": "btnSecondary",
    "ghost":     "btnGhost",
    "danger":    "btnDanger",
}


def make_button(text: str, kind: str = "secondary") -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(_KIND_TO_OBJECT.get(kind, "btnSecondary"))
    btn.setCursor(Qt.PointingHandCursor)
    return btn


def row_buttons(*specs: tuple[str, str]) -> QWidget:
    """
    액션 컬럼 셀에 적합한 소형 버튼 툴바를 구성.
    각 spec은 ``(text, kind)``.  좌측 정렬된 투명 QWidget 반환.
    """
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.setSpacing(6)
    for text, kind in specs:
        lay.addWidget(make_button(text, kind))
    lay.addStretch()
    return w
