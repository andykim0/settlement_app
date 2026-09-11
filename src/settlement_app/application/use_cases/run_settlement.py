# -*- coding: utf-8 -*-
"""
RunSettlementUseCase

정산 계산 오케스트레이션을 위한 플레이스홀더.

TODO: 다음 항목을 settlement-logic-specialist에게 위임:
  - Decimal 기반 지급액 계산
  - 수수료 / 공제 / 세금 적용
  - Python-vs-Excel 검증
  - 반올림 규칙
"""
from __future__ import annotations

import datetime


class RunSettlementUseCase:
    def execute(
        self,
        branch_code: str,
        domain: str,
        target_date: datetime.date,
        excel_path: str,
    ) -> None:
        # TODO: settlement-logic-specialist에게 위임.
        # 기대 인터페이스:
        #   calculate_payout(excel_path, branch_code, domain, target_date) -> SettlementResult
        # SettlementResult 포함 항목:
        #   - 라이더별 Decimal 지급액
        #   - Excel 수식과의 검증 비교 결과
        #   - 불일치 항목의 VerificationFailure 목록
        raise NotImplementedError(
            "RunSettlementUseCase: money-math logic must be implemented by "
            "settlement-logic-specialist."
        )
