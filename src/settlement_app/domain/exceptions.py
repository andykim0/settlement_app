# -*- coding: utf-8 -*-
"""도메인 예외 계층.

모든 예외는 타입이 지정되어 있으며 구조화된 로깅에 충분한 컨텍스트를 포함.
"""
from __future__ import annotations


class SettlementAppError(Exception):
    """정산 앱의 기반 예외."""


class ConfigurationError(SettlementAppError):
    """필수 설정값이 누락되거나 유효하지 않을 때 발생."""


class BranchNotFoundError(SettlementAppError):
    """branch_id가 존재하지 않는 지사를 참조할 때 발생."""
    def __init__(self, branch_id: str) -> None:
        super().__init__(f"Branch not found: {branch_id!r}")
        self.branch_id = branch_id


class RiderNotFoundError(SettlementAppError):
    def __init__(self, rider_id: str) -> None:
        super().__init__(f"Rider not found: {rider_id!r}")
        self.rider_id = rider_id


class ScraperHostNotFoundError(SettlementAppError):
    def __init__(self, scraper_host_id: str) -> None:
        super().__init__(f"ScraperHost not found: {scraper_host_id!r}")
        self.scraper_host_id = scraper_host_id


class DownloadJobError(SettlementAppError):
    """스크래퍼 / 다운로드 작업이 복구 불가 오류에 처할 때 발생."""
    def __init__(self, job_id: str, reason: str) -> None:
        super().__init__(f"Download job {job_id!r} failed: {reason}")
        self.job_id = job_id
        self.reason = reason


class SettlementRunError(SettlementAppError):
    """정산 실행이 오류에 처할 때 발생."""
    def __init__(self, run_id: str, reason: str) -> None:
        super().__init__(f"Settlement run {run_id!r} failed: {reason}")
        self.run_id = run_id
        self.reason = reason


class SettlementVerificationError(SettlementAppError):
    """Python 계산 합계가 Excel 수식 합계와 다를 때 발생.

    TODO: 임계값과 비교 로직은 settlement-logic-specialist가 구현해야 함 —
    이 예외는 불일치 세부 정보를 전달하는 역할만 수행.
    """
    def __init__(self, rider_id: str, field: str, delta: str) -> None:
        super().__init__(
            f"Verification mismatch for rider {rider_id!r}, field {field!r}: Δ={delta}"
        )
        self.rider_id = rider_id
        self.field = field
        self.delta = delta


class AuthenticationError(SettlementAppError):
    """스크래퍼 로그인 또는 OTP 조회가 실패할 때 발생."""
    def __init__(self, domain: str, reason: str) -> None:
        super().__init__(f"Auth failed for domain {domain!r}: {reason}")
        self.domain = domain
        self.reason = reason
