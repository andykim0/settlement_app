# -*- coding: utf-8 -*-
"""Branch 엔티티 — 배달 회사 지사."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AuthMethod(str, Enum):
    EMAIL_OTP = "EMAIL_OTP" #쿠팡 2차 인증방식
    SMS_OTP   = "SMS_OTP" #배민 2차 인증방식


class AccountStatus(str, Enum):
    ACTIVE  = "active"   # 활성
    REVIEW  = "review"   # 검토
    INACTIVE = "inactive" #비활성


@dataclass
class BranchDomainAccount:
    """지사 내 하나의 도메인(baemin / coupang)에 대한 로그인 자격증명."""
    domain: str          # 예: "baemin", "coupang"
    auth_method: AuthMethod
    auth_target: str     # 이메일 주소 또는 마스킹된 전화번호
    scraper_host_id: str       # 예: "HOST-01"
    status: AccountStatus = AccountStatus.ACTIVE
    # NOTE: 인증 정보(비밀번호, OTP 시크릿)는 여기에 저장하지 않음 —
    #       infrastructure/settings (암호화 저장소)에 위치.


@dataclass
class Branch:
    """배달 라이더 회사 지사."""
    branch_id: str       # 예: "Ridestar"
    name: str            # 예: "여의도지사"
    accounts: list[BranchDomainAccount] = field(default_factory=list)
