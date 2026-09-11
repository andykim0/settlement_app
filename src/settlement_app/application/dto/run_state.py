# -*- coding: utf-8 -*-
"""
RunState — 스크래퍼 실행 하나의 경량 인메모리 스냅샷.

Qt 의존성 없이 스레드 간 전달이 가능하도록 일반 dataclass로 유지.
레지스트리(RunRegistry)가 변경 가능한 목록을 소유하며,
소비자는 registry.get_run()을 통해 복사본을 받는다.
"""
from __future__ import annotations

import datetime
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque


def _now() -> datetime.datetime:
    """실행 타임스탬프의 단일 진실 공급원 — UTC 기준.

    Qt 의존성 없이 호출할 수 있도록, 그리고 테스트에서 단일 심볼을
    monkeypatch할 수 있도록 run_registry가 아닌 이 모듈에 위치.
    """
    return datetime.datetime.now(tz=datetime.timezone.utc)


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class RunState:
    run_id: str
    # 고유 식별자, 예: 'coupang-20260513-001'

    source: str
    # 도메인 태그: 'coupang' 또는 'baemin'

    branch_code: str = ""
    # 이 실행이 속한 지사 코드, 예: 'Ridestar'

    status: RunStatus = RunStatus.QUEUED

    started_at: datetime.datetime | None = None
    finished_at: datetime.datetime | None = None

    output_file_paths: list[str] = field(default_factory=list)
    # 다운로드된 Excel 파일의 절대 경로 목록; 성공 시 채워짐

    error_message: str | None = None
    # 마지막 오류 메시지; 실패 시 설정됨

    last_log_lines: Deque[str] = field(
        default_factory=lambda: deque(maxlen=200)
    )
    # 이 실행의 최근 200줄 로그를 담는 링 버퍼

    progress_pct: int = 0
    # 0-100 범위의 대략적인 진행률 (%)

    progress_step: str = ""
    # 사람이 읽을 수 있는 단계 레이블, 예: 'login_started'

    @property
    def runtime_seconds(self) -> float | None:
        """실행이 진행 중이거나 완료된 경우의 실제 경과 시간(초)."""
        if self.started_at is None:
            return None
        end = self.finished_at or _now()
        return (end - self.started_at).total_seconds()
