# -*- coding: utf-8 -*-
"""대시보드 페이지에서 사용하는 DTO."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecentActivityRow:
    time: str        # HH:MM 표시용 문자열 (TODO: datetime 사용 후 presenter에서 포맷)
    step: str
    target: str
    status: str      # badge 색조 키: "info" | "success" | "danger" | "neutral"
    status_label: str


@dataclass(frozen=True)
class RecentErrorRow:
    time: str
    scraper_host_id: str
    branch_domain: str
    message: str


@dataclass(frozen=True)
class DashboardStatsDTO:
    branch_count: int
    excel_done: int
    excel_total: int
    excel_running: int
    excel_error: int
    settlement_done: int
    settlement_total: int
    settlement_fail: int
    send_pending: int
