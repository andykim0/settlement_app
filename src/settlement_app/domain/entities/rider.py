# -*- coding: utf-8 -*-
"""Rider 엔티티."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Rider:
    """시스템에 등록된 배달 라이더."""
    rider_id: str        # 예: "RIDER-1001"
    name: str
    phone: str           # 표시 레이어에서 마스킹
    branch_id: str
