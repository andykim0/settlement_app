# -*- coding: utf-8 -*-
"""정산 실행 및 결과 내역 페이지에서 사용하는 DTO.

Decimal 처리가 필요한 금액 필드는 settlement-logic-specialist 담당으로
TODO 표시됨.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SettlementTargetRow:
    branch_code: str
    excel_path: str
    rider_mapped: int
    rider_total: int
    calc_status: str
    verification_status: str       # badge 색조 키
    verification_label: str
    dynamodb_item_count: int
    run_status: str                # badge 색조 키
    run_status_label: str


@dataclass(frozen=True)
class ValidationFailureRow:
    branch_code: str
    rider_id: str
    field_name: str
    delta: str          # 표시용 문자열 전용 — Decimal 계산은 settlement-logic-specialist 담당


@dataclass(frozen=True)
class ResultBranchRow:
    branch_code: str
    domain: str
    # TODO: settlement-logic-specialist가 total_payout을 Decimal로 제공;
    #       표시 레이어에서 쉼표 구분 문자열로 포맷
    total_payout_display: str
    verification_status: str
    verification_label: str
    excel_files: str
    dynamodb_items: str
    send_status: str
    row_status: str      # badge 색조 키
    row_status_label: str


@dataclass(frozen=True)
class ResultsSummaryDTO:
    settlement_done: int
    settlement_total: int
    sendable_count: int
    verification_fail_count: int
    s3_nas_file_count: int
    dynamodb_daily_count: int
