# -*- coding: utf-8 -*-
"""ScraperHost 엔티티 — Playwright 스크래퍼를 실행하는 물리적 PC."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ScraperHostStatus(str, Enum):
    ONLINE   = "online"   # 온라인
    OFFLINE  = "offline"
    CHECKING = "checking" # 점검


@dataclass
class ScraperHost:
    """시스템에 등록된 ScraperHost 머신."""
    scraper_host_id: str               # 예: "HOST-01"
    supported_domains: list[str] = field(default_factory=list)  # ["baemin", "coupang"]
    otp_receiver: str = ""      # 예: "email 2", "sms 1"
    status: ScraperHostStatus = ScraperHostStatus.ONLINE
