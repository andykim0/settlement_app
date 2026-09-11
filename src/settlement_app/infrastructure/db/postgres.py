# -*- coding: utf-8 -*-
"""
PostgreSQL 커넥션 풀 팩토리.

데이터베이스 이름(delivery_shared / delivery_rider)별로 풀 하나씩 생성.
설정은 AppSettings.db에서 가져오며, 동일한 코드가 다음 환경을 대상으로 함:

  - 로컬 Docker (host=localhost, sslmode=prefer)
  - AWS Aurora (host=<cluster-endpoint>, sslmode=require 또는 verify-full)

레포지토리는 psycopg.connect()를 직접 호출해선 안 됨; 커넥션 제한 준수를 위해
항상 get_pool()을 경유.
"""
from __future__ import annotations

import os
import threading

try:
    from psycopg_pool import ConnectionPool
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "psycopg-pool is not installed. Install with: "
        'pip install -e ".[db]"'
    ) from exc

from settlement_app.infrastructure.settings.app_settings import AppSettings, DatabaseSettings


_pools: dict[str, ConnectionPool] = {}
_lock = threading.Lock()


def _resolve_password(db: DatabaseSettings) -> str:
    """
    설정된 환경변수에서 비밀번호를 읽음.

    로컬 개발 편의: db.host == "localhost"이고 환경변수가 미설정인 경우
    "dev"로 폴백(docker-compose.yml의 POSTGRES_PASSWORD와 일치).
    다른 호스트(RDS, Aurora, staging, prod)에서 환경변수 미설정은 하드 에러.
    """
    password = os.environ.get(db.password_env_var, "")
    if password:
        return password
    if db.host == "localhost":
        return "dev"  # 로컬 개발 전용 fallback — 실제 호스트에는 사용하지 않음
    raise RuntimeError(
        f"Environment variable {db.password_env_var!r} is required when "
        f"db.host={db.host!r} (no dev fallback for non-localhost hosts)."
    )


def _build_conninfo(db: DatabaseSettings, database: str) -> str:
    password = _resolve_password(db)
    return (
        f"host={db.host} port={db.port} dbname={database} "
        f"user={db.user} password={password} "
        f"sslmode={db.sslmode} connect_timeout=5"
    )


def get_pool(settings: AppSettings, database: str) -> ConnectionPool:
    """
    ``database``에 대한 ConnectionPool을 반환 (첫 호출 시 생성).

    사용법:
        with get_pool(settings, settings.db.shared_database).connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")

    풀은 데이터베이스 이름을 키로 하는 프로세스 싱글턴.
    레포지토리는 일반적으로 생성 시 get_pool()을 한 번 호출.
    """
    with _lock:
        if database not in _pools:
            _pools[database] = ConnectionPool(
                _build_conninfo(settings.db, database),
                min_size=1,
                max_size=5,
                open=True,
            )
        return _pools[database]


def close_all_pools() -> None:
    """캐시된 모든 풀을 닫음. 앱 종료 시 호출."""
    with _lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()
