# -*- coding: utf-8 -*-
"""FlatTable — Figma 목업과 일치하는 스타일의 QTableWidget."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem, QWidget,
)

from settlement_app.presentation.theme import COLOR


class FlatTable(QTableWidget):
    """앱의 플랫 테이블 스타일에 맞게 미리 설정된 QTableWidget."""

    def __init__(self, headers: list[str], parent: QWidget | None = None) -> None:
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.verticalHeader().setDefaultSectionSize(40)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setMinimumHeight(34)
        self.horizontalHeader().setStretchLastSection(True)

    def add_row(self, cells: list[str | QWidget]) -> int:
        """
        행 추가. 각 요소는 일반 문자열 또는 QWidget
        (예: badge_cell / row_buttons 위젯).
        새 행 인덱스 반환.
        """
        r = self.rowCount()
        self.insertRow(r)
        for c, content in enumerate(cells):
            if isinstance(content, QWidget):
                self.setCellWidget(r, c, content)
            else:
                item = QTableWidgetItem(str(content))
                item.setForeground(QColor(COLOR["text"]))
                self.setItem(r, c, item)
        return r

    def clear_rows(self) -> None:
        """헤더는 유지하면서 모든 데이터 행 제거."""
        self.setRowCount(0)

    # TODO: 서비스 DTO가 연결되면 populate_from_dto(rows: list[dict]) 추가,
    # 페이지가 테이블 내부를 알지 않고도 갱신할 수 있도록.
