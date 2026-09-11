# server/sms_otp_waiter.py
# ========================
# Android 앱으로부터 SMS JSON을 수신하고 OTP를 추출하는 모듈.
# baemin_login.py 에서 컨텍스트 매니저로 사용한다.
#
# 사용법:
#   with SmsOtpWaiter(host="127.0.0.1", port=8787, keyword_filters=("배민", "인증")) as waiter:
#       page.get_by_role("button", name="인증번호 받기").click()
#       result = waiter.wait_for_code(timeout_seconds=120)
#       print(result.code)  # "123456"

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Iterable
import json


# ─────────────────────────────────────────────────────────────────────────────
# OTP 추출 결과
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OtpResult:
    # 추출된 6자리 인증번호
    code: str
    # 원본 SMS 발신번호
    sender: str
    # 원본 SMS 본문
    body: str


# ─────────────────────────────────────────────────────────────────────────────
# HTTP 핸들러 — Android 앱의 POST 요청 처리
# ─────────────────────────────────────────────────────────────────────────────

class _SmsHandler(BaseHTTPRequestHandler):
    # Android 앱이 POST한 SMS JSON을 수신해서 큐에 저장한다.

    def do_POST(self):
        # Content-Length 만큼 본문을 읽어 JSON으로 파싱한다.
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)
        try:
            data = json.loads(body)
            self.server.received_messages.append(data)
            print(f"[SMS] 수신: {data.get('sender')} | {data.get('body', '')[:60]}")
            self._respond(200, "OK")
        except Exception as e:
            print(f"[SMS] 파싱 오류: {e}")
            self._respond(400, "ERROR")

    def _respond(self, status: int, text: str) -> None:
        self.send_response(status)
        self.end_headers()
        self.wfile.write(text.encode())

    def log_message(self, *args):
        # 기본 HTTP 로그를 억제한다.
        pass


class _SmsHttpServer(HTTPServer):
    # 수신된 SMS 메시지를 저장하는 리스트를 포함한 HTTP 서버.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.received_messages: list[dict] = []


# ─────────────────────────────────────────────────────────────────────────────
# SmsOtpWaiter — 컨텍스트 매니저
# ─────────────────────────────────────────────────────────────────────────────

class SmsOtpWaiter:
    # HTTP 서버를 백그라운드 스레드로 실행하며 Android 앱의 SMS JSON을 기다린다.
    # with 문으로 사용하면 진입 시 서버를 시작하고 종료 시 서버를 멈춘다.

    # OTP 추출 패턴: 4~8자리 숫자
    _CODE_RE = re.compile(r'\b(\d{4,8})\b')

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8787,
        keyword_filters: Iterable[str] = ("배민", "인증"),
        poll_interval: float = 1.0,
    ) -> None:
        self._host           = host
        self._port           = port
        self._keyword_filters = tuple(keyword_filters)
        self._poll_interval  = poll_interval
        self._server: _SmsHttpServer | None  = None
        self._thread: threading.Thread | None = None

    # ── 컨텍스트 매니저 ───────────────────────────────────────────────────────

    def __enter__(self) -> SmsOtpWaiter:
        # HTTP 서버를 백그라운드 스레드로 시작한다.
        self._server = _SmsHttpServer((self._host, self._port), _SmsHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._thread.start()
        print(f"[SMS] 서버 시작: http://{self._host}:{self._port}/sms")
        return self

    def __exit__(self, *_) -> None:
        # HTTP 서버를 종료한다.
        if self._server:
            self._server.shutdown()
            print("[SMS] 서버 종료")

    # ── OTP 대기 ─────────────────────────────────────────────────────────────

    def _matches_keywords(self, body: str) -> bool:
        # SMS 본문이 모든 키워드 필터를 포함하는지 확인한다.
        return all(kw in body for kw in self._keyword_filters)

    def _extract_code(self, body: str) -> str | None:
        # SMS 본문에서 4~8자리 숫자를 추출한다.
        match = self._CODE_RE.search(body)
        return match.group(1) if match else None

    def wait_for_code(self, timeout_seconds: int = 120) -> OtpResult:
        # timeout_seconds 안에 키워드 필터를 통과한 SMS에서 OTP를 반환한다.
        # 시간 초과 시 RuntimeError를 발생시킨다.
        if not self._server:
            raise RuntimeError("서버가 시작되지 않았습니다. with 문으로 사용하세요.")

        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            for msg in reversed(self._server.received_messages):
                body   = msg.get("body", "")
                sender = msg.get("sender", "")

                if not self._matches_keywords(body):
                    continue

                code = self._extract_code(body)
                if code:
                    return OtpResult(code=code, sender=sender, body=body)

            remaining = int(deadline - time.time())
            print(f"[SMS] 인증번호 대기 중 ... ({remaining}초 남음)")
            time.sleep(self._poll_interval)

        raise RuntimeError(
            f"{timeout_seconds}초 안에 인증번호를 받지 못했습니다. "
            f"Android 앱 서버 주소가 http://{self._host}:{self._port}/sms 인지 확인하세요."
        )