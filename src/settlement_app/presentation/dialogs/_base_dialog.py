# -*- coding: utf-8 -*-
"""기본 다이얼로그: 둥근 흰색 카드, 제목 + 부제목, 본문, 푸터."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from settlement_app.presentation.theme import COLOR


class _BaseDialog(QDialog):
    """제목, 선택적 부제목, 본문 영역, 푸터를 갖춘 공통 모달 다이얼로그 베이스."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
        width: int = 560,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint, False)
        self.setModal(True)
        self.setMinimumWidth(width)
        self.setStyleSheet(
            f"QDialog {{ background: {COLOR['surface']}; "
            f"border: 1px solid {COLOR['border']}; border-radius: 12px; }}"
        )

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(28, 24, 28, 24)
        self._root.setSpacing(8)

        self.titleLbl = QLabel(title)
        self.titleLbl.setStyleSheet(
            f"font-size:18px; font-weight:700; color:{COLOR['text']};"
        )
        self._root.addWidget(self.titleLbl)

        if subtitle:
            self.subLbl = QLabel(subtitle)
            self.subLbl.setWordWrap(True)
            self.subLbl.setStyleSheet(
                f"font-size:12px; color:{COLOR['text_muted']};"
            )
            self._root.addWidget(self.subLbl)

        self._root.addSpacing(8)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        self._root.addLayout(self.body)
        self._root.addSpacing(8)

        self.footer = QHBoxLayout()
        self.footer.addStretch()
        self._root.addLayout(self.footer)

    def add_footer(self, *buttons: QWidget) -> None:
        for b in buttons:
            self.footer.addWidget(b)
