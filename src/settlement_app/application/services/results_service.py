# -*- coding: utf-8 -*-
"""
ResultsService — RunRegistry에서 결과 내역 및 정산 대상 행을 도출.

정산 금액 계산은 settlement-logic-specialist 담당이므로 금액 관련 필드는
모두 "-" 플레이스홀더로 남겨둔다.
"""
from __future__ import annotations

import os

from settlement_app.application.dto.run_state import RunState, RunStatus
from settlement_app.application.dto.settlement_dto import ResultBranchRow, SettlementTargetRow
from settlement_app.application.services.run_registry import RunRegistry


# RunStatus → 한국어 레이블
_STATUS_LABEL: dict[RunStatus, str] = {
    RunStatus.QUEUED:    "대기",
    RunStatus.RUNNING:   "스크랩 중",
    RunStatus.SUCCEEDED: "정산 대기",  # 스크랩 성공; 정산은 아직 미완료
    RunStatus.FAILED:    "스크랩 실패",
}

# RunStatus → badge 색조 키
_STATUS_BADGE: dict[RunStatus, str] = {
    RunStatus.QUEUED:    "warning",
    RunStatus.RUNNING:   "info",
    RunStatus.SUCCEEDED: "success",
    RunStatus.FAILED:    "danger",
}


def _excel_files_label(run: RunState) -> str:
    """출력 파일 수를 레이블 문자열로 변환. 파일 없으면 '-'."""
    count = len(run.output_file_paths)
    return f"{count} files" if count > 0 else "-"


def _first_basename(run: RunState) -> str:
    """출력 파일 목록의 첫 항목 파일명(basename). 없으면 '-'."""
    if run.output_file_paths:
        return os.path.basename(run.output_file_paths[0])
    return "-"


class ResultsService:
    def __init__(self, registry: RunRegistry) -> None:
        self._registry = registry

    def list_branch_results(self) -> list[ResultBranchRow]:
        """
        RunRegistry의 모든 실행을 ResultBranchRow 목록으로 변환.

        금액·DynamoDB·S3/NAS 관련 필드는 settlement-logic-specialist가 구현할
        때까지 '-' 플레이스홀더로 유지.
        """
        rows: list[ResultBranchRow] = []
        for run in self._registry.list_runs():
            status = run.status
            rows.append(ResultBranchRow(
                branch_code=run.branch_code or "-",
                domain=run.source,
                # 금액 계산은 settlement-logic-specialist 담당 — 플레이스홀더
                total_payout_display="-",
                # 검증은 settlement-logic-specialist 담당 — 플레이스홀더
                verification_status="neutral",
                verification_label="-",
                excel_files=_excel_files_label(run),
                # DynamoDB 항목 수는 정산 완료 후 채워짐 — 플레이스홀더
                dynamodb_items="-",
                # 전송 상태는 정산 완료 후 채워짐 — 플레이스홀더
                send_status="-",
                row_status=_STATUS_BADGE[status],
                row_status_label=_STATUS_LABEL[status],
            ))
        return rows

    def list_settlement_targets(self) -> list[SettlementTargetRow]:
        """
        스크랩 성공(SUCCEEDED)이지만 정산이 아직 완료되지 않은 실행 목록.

        라이더 수·검증·DynamoDB 필드는 settlement-logic-specialist 담당 —
        플레이스홀더('-')로 남겨둔다.
        """
        rows: list[SettlementTargetRow] = []
        for run in self._registry.list_runs():
            if run.status != RunStatus.SUCCEEDED:
                continue
            rows.append(SettlementTargetRow(
                branch_code=run.branch_code or "-",
                excel_path=_first_basename(run),
                # 라이더 수는 Excel 파싱 후 알 수 있음 — settlement-logic-specialist 담당
                rider_mapped=0,
                rider_total=0,
                calc_status="calc_pending",
                # 검증 결과는 정산 완료 후 채워짐 — 플레이스홀더
                verification_status="neutral",
                verification_label="-",
                # DynamoDB 항목 수는 정산 완료 후 채워짐 — 플레이스홀더
                dynamodb_item_count=0,
                run_status="neutral",
                run_status_label="정산 대기",
            ))
        return rows
