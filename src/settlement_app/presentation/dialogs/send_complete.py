# -*- coding: utf-8 -*-
"""SendCompleteDialog, SendAllOverlay, RunAllOverlay 다이얼로그."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from settlement_app.presentation.dialogs._base_dialog import _BaseDialog
from settlement_app.presentation.theme import COLOR
from settlement_app.presentation.widgets.badge import Badge
from settlement_app.presentation.widgets.buttons import make_button


class SendCompleteDialog(_BaseDialog):
    """전체 전송 작업 완료 후 표시되는 다이얼로그."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "전송 완료",
            "DynamoDB, S3, NAS 전송이 완료되었습니다. 실패 항목은 결과 내역에서 "
            "보류 상태로 유지됩니다.",
            parent,
            width=520,
        )

        # TODO: ResultsService.send_all()이 반환하는 SendResultDTO로 badge 수치 채우기
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(Badge("DynamoDB 1,284 items", "success"))
        row.addWidget(Badge("S3 28 files",          "success"))
        row.addWidget(Badge("NAS 28 files",         "success"))
        row.addStretch()
        self.body.addLayout(row)

        ok = make_button("확인", "primary")
        ok.clicked.connect(self.accept)
        self.add_footer(ok)


# ---- 진행률 오버레이 --------------------------------------------------

class _ProgressOverlay(_BaseDialog):
    """RunAllOverlay와 SendAllOverlay가 공유하는 진행률 오버레이."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        current_step: str,
        blocked_msg: str,
        extra_line: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, subtitle, parent, width=720)

        # TODO: 정적 62% 값을 백그라운드 job의 실제 진행률 시그널로 교체
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(62)
        bar.setTextVisible(False)
        bar.setFixedHeight(10)
        self.body.addWidget(bar)

        step = QLabel(current_step)
        step.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{COLOR['text']};"
        )
        self.body.addWidget(step)

        blocked = QLabel(blocked_msg)
        blocked.setObjectName("mutedNote")
        blocked.setWordWrap(True)
        self.body.addWidget(blocked)

        if extra_line:
            extra = QLabel(extra_line)
            extra.setStyleSheet(
                f"font-size:12px; font-weight:700; color:{COLOR['text']};"
            )
            self.body.addSpacing(8)
            self.body.addWidget(extra)


class RunAllOverlay(_ProgressOverlay):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="전체 프로세스 실행 중",
            subtitle=("작업이 완료될 때까지 주요 설정과 결과 전송을 잠급니다. "
                      "진행률과 현재 ScraperHost/지사/도메인을 계속 보여줍니다."),
            current_step="현재 단계: HOST-01 baemin Excel 다운로드 · 62%",
            blocked_msg="차단 사유: 전체 실행 중에는 설정 변경, 수동 완료, 결과 전송을 막습니다.",
            parent=parent,
        )


class SendAllOverlay(_ProgressOverlay):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="결과 전체 전송 중",
            subtitle=("검증 완료된 결과를 DynamoDB, S3, NAS에 전송합니다. "
                      "전송 중에는 결과 행 수정과 재정산을 잠급니다."),
            current_step="현재 단계: HOST-01 baemin Excel 다운로드 · 62%",
            blocked_msg="차단 사유: 전체 실행 중에는 설정 변경, 수동 완료, 결과 전송을 막습니다.",
            extra_line="전송 대상: DynamoDB settlement_ledger / S3 Raw-Curated-Archive / NAS 날짜별 폴더",
            parent=parent,
        )
