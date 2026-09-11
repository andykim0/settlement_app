# -*- coding: utf-8 -*-
"""
진입점.

실행 방법:
    python -m settlement_app
    # 또는 pip install -e . 이후
    settlement-app
"""
from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from settlement_app.infrastructure.settings.app_settings import load_settings
from settlement_app.presentation.main_window import MainWindow
from settlement_app.presentation.theme import GLOBAL_QSS


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 한국어 친화적 기본 폰트 설정
    f = QFont()
    f.setFamily("Pretendard")
    f.setPointSize(10)
    app.setFont(f)

    app.setStyleSheet(GLOBAL_QSS)

    # TODO: 서비스가 연결되면 settings를 MainWindow / DI 컨테이너에 주입
    _settings = load_settings()

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
