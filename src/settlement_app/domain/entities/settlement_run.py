# -*- coding: utf-8 -*-
"""SettlementRun 엔티티.

참고: 이 엔티티는 실행 생명주기와 결과 메타데이터를 추적.
실제 금액 계산(지급액, 수수료 공제, 반올림, 세금)은 의도적으로 여기에 구현하지 않음.
TODO: 다음 항목을 settlement-logic-specialist에게 위임:
  - Decimal 기반 지급액 계산
  - 수수료/공제 적용
  - Python-vs-Excel 검증 로직
  - 원천징수세 계산
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class SettlementStatus(str, Enum):
    CREATED         = "created"
    RUNNING         = "running"           # Python 계산 실행 중
    CALC_DONE       = "calc_done"
    VERIFICATION_OK = "verification_ok"
    VERIFICATION_FAIL = "verification_fail"
    COMPLETED       = "completed"         # xlsx 저장 완료


@dataclass
class VerificationFailure:
    """Python-vs-Excel 비교에서 불일치한 항목 하나."""
    rider_id: str
    field_name: str     # 예: "net_amount", "lease_fee", "withholding_tax"
    delta: str          # 포맷된 차이값, 예: "-3,200" — 표시 전용
    # NOTE: 프로그래밍적 사용을 위한 실제 Decimal 델타는 settlement-logic-specialist 담당


@dataclass
class SettlementRun:
    """
    대상 날짜의 branch / domain에 대한 정산 실행 하나를 추적.
    금액 필드는 프로젝트 규약에 따라 Decimal 사용.
    """
    run_id: str
    branch_code: str
    domain: str
    target_date: datetime.date
    excel_path: str         # settings.excel_download_dir 기준 상대 경로
    status: SettlementStatus = SettlementStatus.CREATED
    rider_mapped: int = 0
    rider_total: int = 0
    dynamodb_item_count: int = 0
    # TODO: 
    total_payout: Decimal = field(default_factory=lambda: Decimal("0"))
    verification_failures: list[VerificationFailure] = field(default_factory=list)
    started_at: datetime.datetime | None = None
    finished_at: datetime.datetime | None = None
