# -*- coding: utf-8 -*-
"""소형 프레젠테이션 헬퍼 모음."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QProgressBar, QWidget,
)

from settlement_app.presentation.theme import COLOR


class VSpacer(QWidget):
    def __init__(self, height: int = 8, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)


def progress_cell(percent: int) -> QWidget:
    """테이블 셀에 적합한 소형 진행률 바 + 퍼센트 레이블."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(8, 6, 8, 6)
    lay.setSpacing(8)

    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(percent)
    bar.setTextVisible(False)
    bar.setFixedHeight(8)
    lay.addWidget(bar, 1)

    pct = QLabel(f"{percent}%")
    pct.setStyleSheet(f"color:{COLOR['text_secondary']}; font-size:11px;")
    lay.addWidget(pct)
    return w


def soft_shadow(widget: QWidget) -> None:
    """위젯(예: 카드)에 은은한 드롭 섀도 효과 적용."""
    e = QGraphicsDropShadowEffect(widget)
    e.setBlurRadius(18)
    e.setOffset(0, 2)
    e.setColor(QColor(15, 23, 42, 18))
    widget.setGraphicsEffect(e)
