# -*- coding: utf-8 -*-
"""DashboardService — RunRegistry에서 최근 활동/오류를 도출.

StatCard가 실시간 갱신을 위한 update_value() 슬롯을 노출하면
실제 집계 수치로 교체할 예정이며, 현재는 stat-card 수치가 스텁 상태.
"""
from __future__ import annotations

import datetime

from settlement_app.application.dto.dashboard_dto import (
    DashboardStatsDTO,
    RecentActivityRow,
    RecentErrorRow,
)
from settlement_app.application.dto.run_state import RunState, RunStatus
from settlement_app.application.services.run_registry import RunRegistry


_EPOCH = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def _sort_key(state: RunState) -> datetime.datetime:
    """가장 최신 이벤트 타임스탬프; 없는 값은 맨 앞으로 정렬."""
    return state.finished_at or state.started_at or _EPOCH


_STATUS_TO_BADGE: dict[RunStatus, tuple[str, str]] = {
    # RunStatus → (한국어 레이블, badge 색조)
    RunStatus.QUEUED:    ("대기",     "neutral"),
    RunStatus.RUNNING:   ("실행 중",  "info"),
    RunStatus.SUCCEEDED: ("실행완료", "success"),
    RunStatus.FAILED:    ("실패",     "danger"),
}


def _fmt_hhmm(state: RunState) -> str:
    ts = state.finished_at or state.started_at
    return ts.strftime("%H:%M") if ts else "--:--"


def _activity_from(state: RunState) -> RecentActivityRow:
    label, tone = _STATUS_TO_BADGE.get(state.status, ("?", "neutral"))
    return RecentActivityRow(
        time=_fmt_hhmm(state),
        step="엑셀 다운로드",
        target=f"local / {state.source}",
        status=tone,
        status_label=label,
    )


def _error_from(state: RunState) -> RecentErrorRow:
    return RecentErrorRow(
        time=_fmt_hhmm(state),
        scraper_host_id="HOST-LOCAL",
        branch_domain=f"local / {state.source}",
        message=state.error_message or "Unknown error",
    )


class DashboardService:
    def __init__(self, registry: RunRegistry) -> None:
        self._registry = registry

    def get_stats(self) -> DashboardStatsDTO:
        """RunRegistry에서 집계 수치를 도출해 반환.

        정산 관련 수치(settlement_done, settlement_fail, send_pending)는
        settlement-logic-specialist 담당이므로 0 플레이스홀더 유지.
        """
        runs = self._registry.list_runs()

        # 고유 지사 코드 집합; 실행이 없으면 기본값 1(Ridestar)
        unique_branches = {r.branch_code for r in runs if r.branch_code}
        branch_count = len(unique_branches) if unique_branches else 1

        excel_done = sum(1 for r in runs if r.status == RunStatus.SUCCEEDED)
        excel_total = len(runs)
        excel_running = sum(1 for r in runs if r.status == RunStatus.RUNNING)
        excel_error = sum(1 for r in runs if r.status == RunStatus.FAILED)

        # 정산 수치는 settlement-logic-specialist가 구현할 때까지 플레이스홀더
        return DashboardStatsDTO(
            branch_count=branch_count,
            excel_done=excel_done,
            excel_total=excel_total,
            excel_running=excel_running,
            excel_error=excel_error,
            settlement_done=0,             # 정산 미구현 — 플레이스홀더
            settlement_total=excel_done,   # 스크랩 성공 건수 = 정산 대상
            settlement_fail=0,             # 정산 미구현 — 플레이스홀더
            send_pending=0,                # 정산 미구현 — 플레이스홀더
        )

    def get_recent_activities(self, limit: int = 10) -> list[RecentActivityRow]:
        """최신순으로 최대 `limit`개 행 반환."""
        runs = sorted(
            self._registry.list_runs(),
            key=_sort_key,
            reverse=True,
        )
        return [_activity_from(s) for s in runs[:limit]]

    def get_recent_errors(self, limit: int = 10) -> list[RecentErrorRow]:
        """실패한 실행만, 최신순으로 최대 `limit`개 행 반환."""
        failed = [s for s in self._registry.list_runs() if s.status == RunStatus.FAILED]
        failed.sort(key=_sort_key, reverse=True)
        return [_error_from(s) for s in failed[:limit]]
