# -*- coding: utf-8 -*-
"""모든 페이지 위젯에서 공유하는 페이지 레이아웃 헬퍼."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)


def page_header(title: str, subtitle: str, *action_buttons: QPushButton) -> QWidget:
    """표준 페이지 제목 / 부제목 / 액션 버튼 바 구성."""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(2)

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    title_lbl = QLabel(title)
    title_lbl.setObjectName("pageTitle")
    row.addWidget(title_lbl)
    row.addStretch()
    for b in action_buttons:
        row.addWidget(b)
    v.addLayout(row)

    sub = QLabel(subtitle)
    sub.setObjectName("pageSubtitle")
    v.addWidget(sub)
    return w


def page_scaffold() -> tuple[QWidget, QVBoxLayout]:
    """일관된 페이지 패딩을 적용한 (outer_widget, content_layout) 반환."""
    outer = QWidget()
    box = QVBoxLayout(outer)
    box.setContentsMargins(40, 32, 40, 32)
    box.setSpacing(20)
    return outer, box
