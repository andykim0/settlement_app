# -*- coding: utf-8 -*-
"""Card 및 StatCard 위젯."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from settlement_app.presentation.theme import COLOR


class StatCard(QFrame):
    """KPI 통계 카드: 레이블 / 큰 값 / 선택적 푸터 라인."""

    def __init__(
        self,
        label: str,
        value: str,
        foot: str = "",
        foot_tone: str = "muted",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setMinimumHeight(96)

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(4)

        self.lbl = QLabel(label)
        self.lbl.setObjectName("statLabel")
        self.val = QLabel(value)
        self.val.setObjectName("statValue")
        v.addWidget(self.lbl)
        v.addWidget(self.val)

        if foot:
            foot_obj = {
                "info":  "statFootInfo",
                "error": "statFootError",
                "ok":    "statFootOk",
                "muted": "statFoot",
            }.get(foot_tone, "statFoot")
            self.foot = QLabel(foot)
            self.foot.setObjectName(foot_obj)
            self.foot.setWordWrap(True)
            v.addWidget(self.foot)
        v.addStretch()

    # TODO: presenter가 위젯을 재구성하지 않고 실시간 데이터를 밀어 넣을 수 있도록
    # update_value(value, foot) 슬롯을 노출. 현재는 생성 시에만 값이 설정됨.


class Card(QFrame):
    """선택적 제목과 본문 / 헤더 레이아웃을 갖춘 둥근 박스."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(20, 16, 20, 16)
        self._outer.setSpacing(12)

        self.header = QHBoxLayout()
        self.header.setContentsMargins(0, 0, 0, 0)
        if title:
            self.titleLabel = QLabel(title)
            self.titleLabel.setObjectName("cardTitle")
            self.header.addWidget(self.titleLabel)
        self.header.addStretch()
        self._outer.addLayout(self.header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        self._outer.addLayout(self.body)

    def addHeaderWidget(self, w: QWidget) -> None:
        self.header.addWidget(w)
