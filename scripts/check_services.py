#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_services.py — 로컬 Docker 서비스에 접근 가능한지 확인.

사용법:
    python scripts/check_services.py

두 Postgres 데이터베이스가 정상 응답하면 0, 그렇지 않으면 1로 종료.

확인 항목:
  - Postgres @ delivery_shared (branch 테이블 행 수 조회)
  - Postgres @ delivery_rider  (rider 테이블 행 수 조회)

의존성 (pip install -e ".[db]" 으로 설치):
    psycopg[binary,pool]>=3.2
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from settlement_app.infrastructure.settings.app_settings import load_settings  # noqa: E402


def _resolve_password(host: str, password_env_var: str) -> str | None:
    pw = os.environ.get(password_env_var, "")
    if pw:
        return pw
    if host == "localhost":
        return "dev"  # 로컬 개발 전용 fallback (docker-compose와 일치)
    return None


def _check_postgres_db(
    host: str, port: int, database: str, user: str,
    password_env_var: str, sslmode: str, count_table: str,
) -> bool:
    """count_table에 SELECT count(*)를 실행. 성공하면 True 반환."""
    try:
        import psycopg  # type: ignore[import]
    except ImportError:
        print(
            '[FAIL] psycopg not installed — run: pip install -e ".[db]"',
            file=sys.stderr,
        )
        return False

    password = _resolve_password(host, password_env_var)
    if password is None:
        print(
            f"[FAIL] postgres ({database}) — env var {password_env_var!r} unset "
            f"and host is not localhost",
            file=sys.stderr,
        )
        return False

    conninfo = (
        f"host={host} port={port} dbname={database} "
        f"user={user} password={password} sslmode={sslmode} connect_timeout=5"
    )
    try:
        with psycopg.connect(conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute(f'SELECT count(*) FROM "{count_table}"')
                (n,) = cur.fetchone()
        print(f"[OK]   postgres  {database}  {count_table}={n} rows")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] postgres  {database} — {exc}", file=sys.stderr)
        return False


def main() -> int:
    settings = load_settings()
    db = settings.db

    shared_ok = _check_postgres_db(
        host=db.host, port=db.port, database=db.shared_database,
        user=db.user, password_env_var=db.password_env_var,
        sslmode=db.sslmode, count_table="branch",
    )
    rider_ok = _check_postgres_db(
        host=db.host, port=db.port, database=db.rider_database,
        user=db.user, password_env_var=db.password_env_var,
        sslmode=db.sslmode, count_table="rider",
    )

    return 0 if (shared_ok and rider_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
