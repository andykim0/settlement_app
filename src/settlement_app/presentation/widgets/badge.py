# -*- coding: utf-8 -*-
"""상태 뱃지 위젯 및 셀 헬퍼."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from settlement_app.presentation.theme import COLOR

_BADGE_STYLES: dict[str, tuple[str, str]] = {
    "info":    (COLOR["info_bg"],    COLOR["info_fg"]),
    "success": (COLOR["success_bg"], COLOR["success_fg"]),
    "danger":  (COLOR["danger_bg"],  COLOR["danger_fg"]),
    "warning": (COLOR["warning_bg"], COLOR["warning_fg"]),
    "neutral": (COLOR["neutral_bg"], COLOR["neutral_fg"]),
}


class Badge(QLabel):
    """작은 알약 형태의 상태 뱃지."""

    def __init__(self, text: str, tone: str = "neutral", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        bg, fg = _BADGE_STYLES.get(tone, _BADGE_STYLES["neutral"])
        self.setStyleSheet(
            f"""
            QLabel {{
                background: {bg};
                color: {fg};
                border-radius: 10px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            """
        )
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)


def badge_cell(text: str, tone: str = "neutral") -> QWidget:
    """Badge를 셀 친화적인 위젯으로 감쌈(좌측 정렬, 패딩 포함)."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(8, 4, 8, 4)
    lay.addWidget(Badge(text, tone))
    lay.addStretch()
    return w
