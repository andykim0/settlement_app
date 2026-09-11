#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coupang_imap_otp.py — Coupang 스크래퍼용 IMAP 기반 OTP 조회.

6자리 코드 추출 로직은 coupang_email_verifier_v1_2.py와 동일:
  - 제목 필터: 한국어 또는 영어 Coupang OTP 제목과 매칭
  - 본문 정규식: re.compile(r'\\b(\\d{6})\\b')

저장 모델
---------
이메일 주소로 연결된 두 개의 별도 저장소:
  메타데이터  →  ~/.coupang_imap_otp/accounts.json   (coupang_id, email,
                                                      provider, status,
                                                      timestamps, contact)
  비밀값     →  OS 키체인 (`keyring` 사용)            (앱 비밀번호만)

빠른 시작
---------
  pip install imap-tools keyring
  python3 -m settlement_app.infrastructure.scrapers.coupang_imap_otp register
  python3 -m settlement_app.infrastructure.scrapers.coupang_imap_otp list
  python3 -m settlement_app.infrastructure.scrapers.coupang_imap_otp test ridestar211p
  python3 -m settlement_app.infrastructure.scrapers.coupang_imap_otp get  ridestar211p

settlement_app 통합
-------------------
  from settlement_app.infrastructure.scrapers.coupang_imap_otp import (
      get_code_for_coupang_id,
  )
  code = get_code_for_coupang_id(coupang_id, request_time=request_time)
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

try:
    from imap_tools import AND, MailBox
    from imap_tools.errors import ImapToolsError, MailboxLoginError
except ImportError as _exc:
    print(
        f"ERROR: imap-tools import failed: {_exc}\n"
        f"Install with:  pip install imap-tools",
        file=sys.stderr,
    )
    sys.exit(2)

try:
    import keyring
    import keyring.errors
except ImportError:
    print(
        "ERROR: `keyring` package is required.\n"
        "Install it with:  pip install keyring",
        file=sys.stderr,
    )
    sys.exit(2)


logger = logging.getLogger("coupang_imap_otp")
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / ".coupang_imap_otp" / "accounts.json"
KEYRING_SERVICE = "coupang_imap_otp"

# 쿠팡은 OTP 메일을 한국어 또는 영어 제목으로 발송한다.
DEFAULT_OTP_SUBJECT_HINTS: tuple[str, ...] = (
    "이메일 인증번호가 도착하였습니다",
    "Your email verification code has arrived",
)

# Provider → IMAP 엔드포인트. 코드 수정 없이 새 provider를 여기에 추가.
PROVIDERS: dict[str, dict] = {
    "naver":   {"host": "imap.naver.com",        "port": 993},
    "gmail":   {"host": "imap.gmail.com",        "port": 993},
    "outlook": {"host": "outlook.office365.com", "port": 993},
    "daum":    {"host": "imap.daum.net",         "port": 993},
}

_DOMAIN_TO_PROVIDER = {
    "naver.com": "naver",
    "gmail.com": "gmail", "googlemail.com": "gmail",
    "outlook.com": "outlook", "hotmail.com": "outlook", "live.com": "outlook",
    "daum.net": "daum", "hanmail.net": "daum", "kakao.com": "daum",
}


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------

@dataclass
class Account:
    """지사 메일함의 비밀이 아닌 메타데이터.

    앱 비밀번호는 OS 키체인에 위치 — 이 구조체에도, JSON 파일에도,
    로그 라인에도 절대 포함하지 않음.
    """
    coupang_id: str
    email: str
    provider: str
    status: str = "active"            # active | disabled | pending_setup | invalid
    created_at: str = ""
    last_login_at: str = ""
    last_error: str = ""
    contact: str = ""
    notes: str = ""

    def imap_host(self) -> str:
        return PROVIDERS[self.provider]["host"]

    def imap_port(self) -> int:
        return PROVIDERS[self.provider]["port"]


# ---------------------------------------------------------------------------
# 메타데이터 저장소 (JSON 파일, 퍼미션 0600)
# ---------------------------------------------------------------------------

def load_accounts() -> dict[str, Account]:
    if not CONFIG_PATH.exists():
        return {}
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    accounts: dict[str, Account] = {}
    known_fields = {f.name for f in Account.__dataclass_fields__.values()}
    for cid, data in raw.items():
        # 허용적 로드: 향후 필드 추가 시 오류가 발생하지 않도록 알 수 없는 키 무시
        clean = {k: v for k, v in data.items() if k in known_fields}
        accounts[cid] = Account(**clean)
    return accounts


def save_accounts(accounts: dict[str, Account]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {cid: asdict(acc) for cid, acc in accounts.items()}
    CONFIG_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    # 이메일→지사 매핑이 전체 공개되지 않도록 소유자만 읽을 수 있게 제한.
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass  # Windows는 POSIX 퍼미션을 지원하지 않음


# ---------------------------------------------------------------------------
# 비밀 저장소 (OS 키체인)
# ---------------------------------------------------------------------------

def set_app_password(email_addr: str, app_password: str) -> None:
    keyring.set_password(KEYRING_SERVICE, email_addr, app_password)


def get_app_password(email_addr: str) -> Optional[str]:
    return keyring.get_password(KEYRING_SERVICE, email_addr)


def delete_app_password(email_addr: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, email_addr)
    except keyring.errors.PasswordDeleteError:
        pass  # 이미 없는 경우 — 무시


# ---------------------------------------------------------------------------
# 핵심: IMAP OTP 조회
# ---------------------------------------------------------------------------

# 레거시 Playwright 검증기와 동일한 정규식 — 메일 본문에서 독립된
# 6자리 숫자를 추출. CSS 제거 후(_extract_body_text 참조) 정확히 하나만 남는다.
CODE_PATTERN = re.compile(r"\b(\d{6})\b")

# CODE_PATTERN 실행 전 HTML 노이즈를 제거하는 패턴. 중요:
# 쿠팡 HTML 메일에는 `color:#333333;` 같은 CSS가 포함되어 있어,
# style 속성을 제거하지 않으면 \b\d{6}\b가 CSS 색상값과 매칭되어
# CSS 색상을 OTP로 제출하게 된다. (실제로 수 주간 발생했던 문제.)
_STYLE_BLOCK_RE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_STYLE_ATTR_RE  = re.compile(r"""\sstyle\s*=\s*(?:"[^"]*"|'[^']*')""", re.IGNORECASE)
_TAG_RE         = re.compile(r"<[^>]+>")


def _extract_body_text(msg) -> str:
    """CSS를 제거한 이메일 본문의 가시 텍스트 반환.

    우선순위:
      1. msg.text — multipart/alternative 일반 텍스트 파트 (CSS 없음)
      2. <style> 블록과 style="..." 속성을 제거한 msg.html,
         이후 HTML 태그 제거.
    """
    if msg.text:
        return msg.text
    html = msg.html or ""
    html = _STYLE_BLOCK_RE.sub(" ", html)
    html = _STYLE_ATTR_RE.sub("", html)
    return _TAG_RE.sub(" ", html)


def _subject_matches(subject: str, hints: tuple[str, ...]) -> bool:
    """힌트 문자열 중 하나라도 제목에 포함되면(부분 문자열 매칭) True."""
    return any(hint in subject for hint in hints)


def _is_fresh_match(
    msg,  # imap_tools.MailMessage
    subject_hints: tuple[str, ...],
    request_time_utc: datetime.datetime,
    grace_seconds: int,
) -> Optional[str]:
    """msg가 신선한 OTP이면 6자리 코드 반환; 아니면 None."""
    if not _subject_matches(msg.subject or "", subject_hints):
        return None
    msg_date = msg.date
    if msg_date is None:
        return None
    # UTC로 정규화. Python 3.6+: naive datetime.astimezone(tz)는
    # naive datetime을 시스템 로컬 타임존으로 간주하여 올바르게 변환.
    msg_date_utc = msg_date.astimezone(datetime.timezone.utc)
    cutoff = request_time_utc - datetime.timedelta(seconds=grace_seconds)
    if msg_date_utc < cutoff:
        return None
    body = _extract_body_text(msg)
    m = CODE_PATTERN.search(body)
    return m.group(1) if m else None


def get_otp_via_imap(
    account: Account,
    app_password: str,
    request_time: datetime.datetime,
    *,
    subject_hints: tuple[str, ...] = DEFAULT_OTP_SUBJECT_HINTS,
    poll_interval_sec: float = 5.0,
    max_wait_sec: float = 180.0,
    grace_seconds: int = 90,  # unused since switching to UID snapshot
) -> str:
    """계정 INBOX에서 가장 최신 OTP를 가져옴.

    OTP가 나타나거나 `max_wait_sec`이 경과할 때까지 `poll_interval_sec`마다
    폴링 (OTP 메일이 요청보다 몇 초 늦게 도착하는 경우가 있음).

    예외:
        RuntimeError: 인증 실패 또는 제한 시간 내에 일치하는 OTP가 없는 경우.
    """
    host, port = account.imap_host(), account.imap_port()

    # 레거시 검증기(_search_naver)와 동일: Date 헤더가 request_time - 60s 이상이면
    # "신선한" 후보로 간주. coupang_core.py의 naive datetime은
    # .astimezone()에 의해 로컬 시간으로 처리된다.
    request_utc = request_time.astimezone(datetime.timezone.utc)
    cutoff_utc = request_utc - datetime.timedelta(seconds=grace_seconds)
    logger.info(
        "Looking for fresh Coupang OTP: request=%s cutoff=%s grace=%ds",
        request_utc.isoformat(), cutoff_utc.isoformat(), grace_seconds,
    )

    deadline = time.monotonic() + max_wait_sec
    last_error: Optional[str] = None
    poll_n = 0

    while True:
        poll_n += 1
        try:
            with MailBox(host, port).login(
                account.email, app_password, initial_folder="INBOX",
            ) as mb:
                # 최신 20개 메시지를 최신순으로 가져옴. 레거시 검증기가
                # 네이버 검색 결과 페이지를 열고 상위 행을 읽는 방식과 동일.
                considered = []
                for msg in mb.fetch(
                    reverse=True, limit=20, mark_seen=False, bulk=False,
                ):
                    subj = msg.subject or ""
                    if msg.date is None:
                        continue
                    msg_utc = msg.date.astimezone(datetime.timezone.utc)
                    considered.append((msg.uid, msg_utc, subj))
                    if not _subject_matches(subj, subject_hints):
                        continue
                    if msg_utc < cutoff_utc:
                        # request_time - grace보다 오래된 메일; 원하는 것이 아님.
                        # 비OTP 메일(예: 두 OTP 사이의 배민 메일)과 섞인
                        # 더 최신 메일이 있을 수 있으므로 계속 스캔.
                        continue
                    body = _extract_body_text(msg)
                    m = CODE_PATTERN.search(body)
                    if m:
                        logger.info(
                            "FOUND OTP %s on poll #%d (UID=%s, date=%s, subject=%r)",
                            m.group(1), poll_n, msg.uid, msg_utc.isoformat(), subj,
                        )
                        return m.group(1)

                # 아직 신선한 OTP 없음 — 디버깅용으로 확인한 항목 표시
                logger.info(
                    "Poll #%d: no fresh OTP yet (newest 5 considered: %s)",
                    poll_n,
                    [(u, d.isoformat(), s[:40]) for u, d, s in considered[:5]],
                )

        except MailboxLoginError as exc:
            # 인증 오류는 치명적 — 계속 폴링해도 의미 없음
            raise RuntimeError(
                f"IMAP 로그인 실패 ({account.email}): {exc}\n"
                f"확인 사항:\n"
                f"  1) Naver: 메일 설정에서 IMAP 사용 켜기\n"
                f"  2) 앱 비밀번호가 정확한지 (일반 비밀번호 아님)\n"
                f"  3) 계정에 2단계 인증이 켜져 있는지"
            ) from exc
        except ImapToolsError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("IMAP poll error: %s", last_error)

        if time.monotonic() >= deadline:
            msg = (
                f"OTP 미수신: {account.email} INBOX 에서 "
                f"{max_wait_sec:.0f}초 안에 쿠팡 인증 메일을 찾지 못함"
            )
            if last_error:
                msg += f" (마지막 오류: {last_error})"
            raise RuntimeError(msg)

        time.sleep(poll_interval_sec)


# ---------------------------------------------------------------------------
# 공개 진입점 — 검증기의 get_code_sync(branch_email, ...) 대응
# ---------------------------------------------------------------------------

def get_code_for_coupang_id(
    coupang_id: str,
    request_time: Optional[datetime.datetime] = None,
) -> str:
    """coupang_email_verifier.get_code_sync()의 드롭인 대체제.

    계정을 조회하고, 키체인에서 앱 비밀번호를 가져오고, IMAP으로 OTP를 조회한 뒤
    성공 시 last_login_at을 갱신.
    """
    if request_time is None:
        request_time = datetime.datetime.now(tz=datetime.timezone.utc)

    accounts = load_accounts()
    account = accounts.get(coupang_id)
    if account is None:
        raise RuntimeError(
            f"등록되지 않은 coupang_id={coupang_id!r}. "
            f"먼저 `python -m settlement_app.infrastructure.scrapers."
            f"coupang_imap_otp register` 로 등록하세요."
        )
    if account.status != "active":
        raise RuntimeError(
            f"계정 상태가 active 가 아님 (status={account.status}, "
            f"last_error={account.last_error!r})"
        )

    app_pw = get_app_password(account.email)
    if not app_pw:
        raise RuntimeError(
            f"키체인에 앱 비밀번호가 없습니다 ({account.email}). "
            f"`register` 를 다시 실행하세요."
        )

    try:
        code = get_otp_via_imap(account, app_pw, request_time)
    except Exception as exc:
        account.last_error = f"{type(exc).__name__}: {exc}"
        accounts[coupang_id] = account
        save_accounts(accounts)
        raise

    account.last_login_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    account.last_error = ""
    accounts[coupang_id] = account
    save_accounts(accounts)
    return code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _detect_provider(email_addr: str) -> str:
    domain = email_addr.split("@")[-1].lower()
    return _DOMAIN_TO_PROVIDER.get(domain, "")


def cmd_register(args: argparse.Namespace) -> int:
    accounts = load_accounts()

    coupang_id = (args.coupang_id or
                  input("Coupang ID (예: ridestar211p): ").strip())
    email_addr = (args.email or
                  input("Branch email (예: ridestarco@naver.com): ").strip())
    provider = args.provider or _detect_provider(email_addr)
    if not provider:
        provider = input(f"Provider [{'|'.join(PROVIDERS)}]: ").strip()
    if provider not in PROVIDERS:
        print(f"지원하지 않는 provider: {provider!r}. "
              f"지원: {sorted(PROVIDERS)}", file=sys.stderr)
        return 2

    app_pw = args.app_password or getpass.getpass(
        "App password (네이버 메일 → 환경설정 → 앱 비밀번호; 입력 숨김): "
    ).strip()
    if not app_pw:
        print("ERROR: 앱 비밀번호가 필요합니다", file=sys.stderr)
        return 2

    contact = args.contact or input("Contact (선택, 비워도 됨): ").strip()

    accounts[coupang_id] = Account(
        coupang_id=coupang_id,
        email=email_addr,
        provider=provider,
        contact=contact,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
    )
    save_accounts(accounts)
    set_app_password(email_addr, app_pw)

    print(f"등록 완료: {coupang_id} → {email_addr} ({provider})")
    print(f"  메타데이터: {CONFIG_PATH}")
    print(f"  앱 비밀번호: OS 키체인 (service='{KEYRING_SERVICE}', user='{email_addr}')")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    accounts = load_accounts()
    if not accounts:
        print("(등록된 계정 없음)")
        return 0
    print(f"{'coupang_id':<20} {'email':<30} {'provider':<10} "
          f"{'status':<10} {'secret':<7} last_login")
    print("-" * 100)
    for acc in accounts.values():
        secret = "✓" if get_app_password(acc.email) else "✗"
        print(f"{acc.coupang_id:<20} {acc.email:<30} {acc.provider:<10} "
              f"{acc.status:<10} {secret:<7} {acc.last_login_at or '(never)'}")
        if acc.last_error:
            print(f"  ↳ last_error: {acc.last_error}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    accounts = load_accounts()
    if args.coupang_id not in accounts:
        print(f"등록되지 않음: {args.coupang_id}", file=sys.stderr)
        return 1
    acc = accounts.pop(args.coupang_id)
    delete_app_password(acc.email)
    save_accounts(accounts)
    print(f"삭제 완료: {args.coupang_id} ({acc.email})  키체인 항목도 제거됨")
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """OTP 조회 없이 INBOX에 연결하여 자격증명을 검증."""
    accounts = load_accounts()
    acc = accounts.get(args.coupang_id)
    if acc is None:
        print(f"등록되지 않음: {args.coupang_id}", file=sys.stderr)
        return 1
    app_pw = get_app_password(acc.email)
    if not app_pw:
        print(f"키체인에 앱 비밀번호 없음: {acc.email}", file=sys.stderr)
        return 1
    try:
        with MailBox(acc.imap_host(), acc.imap_port()).login(
            acc.email, app_pw, initial_folder="INBOX",
        ) as mb:
            status = mb.folder.status("INBOX", ["MESSAGES"])
            count = status.get("MESSAGES") or status.get(b"MESSAGES") or 0
            print(f"✓ {acc.email}  로그인 성공  INBOX 메시지 수: {count}")
            return 0
    except MailboxLoginError as exc:
        print(f"✗ 로그인 실패: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"✗ 연결 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def cmd_get(args: argparse.Namespace) -> int:
    if args.since:
        request_time = datetime.datetime.fromisoformat(args.since)
        if request_time.tzinfo is None:
            request_time = request_time.replace(tzinfo=datetime.timezone.utc)
    else:
        request_time = datetime.datetime.now(tz=datetime.timezone.utc)
    try:
        code = get_code_for_coupang_id(args.coupang_id, request_time=request_time)
        print(code)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="coupang_imap_otp",
        description="IMAP-based OTP retrieval for the Coupang scraper.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="신규 지사 계정 등록 (이메일 + 앱 비밀번호)")
    r.add_argument("--coupang-id", dest="coupang_id")
    r.add_argument("--email")
    r.add_argument("--provider", choices=sorted(PROVIDERS))
    r.add_argument("--contact")
    r.add_argument("--app-password", dest="app_password",
                   help="(테스트용 — 대화식 입력을 권장)")
    r.set_defaults(func=cmd_register)

    l = sub.add_parser("list", help="등록된 계정 목록")
    l.set_defaults(func=cmd_list)

    rm = sub.add_parser("remove", help="등록된 계정 삭제 (키체인 항목도 함께 삭제)")
    rm.add_argument("coupang_id")
    rm.set_defaults(func=cmd_remove)

    t = sub.add_parser("test", help="OTP 없이 IMAP 로그인만 확인")
    t.add_argument("coupang_id")
    t.set_defaults(func=cmd_test)

    g = sub.add_parser("get", help="OTP 한 건 가져오기 (실제 인증코드 메일 필요)")
    g.add_argument("coupang_id")
    g.add_argument("--since", help="ISO 시각 (기본: 지금)")
    g.set_defaults(func=cmd_get)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
