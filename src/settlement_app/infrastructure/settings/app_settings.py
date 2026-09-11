# -*- coding: utf-8 -*-
"""
AppSettings — 모든 런타임 설정을 하나의 타입 지정 모델로.

시작 시 JSON 설정 파일 또는 환경변수에서 한 번만 로드.
소스 코드에 경로나 자격증명을 절대 하드코딩하지 않음 — 여기에 정의하고
파일이나 환경변수에서 로드.

민감한 값(DB 비밀번호, AES 키)은 암호화된 파일(예: keyring 또는 전용 .key 파일)에
저장해야 함 — 일반 JSON에는 저장 금지.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Type, TypeVar, get_type_hints

logger = logging.getLogger(__name__)

_DC = TypeVar("_DC")


@dataclass
class DatabaseSettings:
    # 클러스터 수준 연결 (동일 Aurora 클러스터가 두 데이터베이스를 호스팅).
    # AWS 전환 시: host, sslmode, password 환경변수 값을 변경.
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password_env_var: str = "SETTLEMENT_DB_PASSWORD"
    # "prefer"는 로컬 Docker용; RDS/Aurora에서는 "require" 또는 "verify-full"로 변경.
    sslmode: str = "prefer"
    # 클러스터 내 논리적 데이터베이스 이름.
    shared_database: str = "delivery_shared"
    rider_database: str = "delivery_rider"
    # 암호화 컬럼용 AES 키 파일 경로; KMS 연결 시 설정.
    aes_key_path: str = ""


@dataclass
class StorageSettings:
    local_excel_dir: str = ""    # 절대 경로; 코드 전반에서 pathlib.Path 사용
    nas_base_dir: str = ""
    s3_bucket: str = "delivery-settlement"


@dataclass
class ScraperSettings:
    baemin_id: str = ""
    # NOTE: baemin_password는 환경변수 BAEMIN_PASSWORD에서 읽음 — 이 파일에 저장하지 않음
    coupang_id: str = ""
    # 단일 사용자 모드의 활성 지사 코드
    active_branch_code: str = "Ridestar"
    sms_server_host: str = "127.0.0.1"
    sms_server_port: int = 8787
    otp_timeout_seconds: int = 120
    step_timeout_seconds: int = 180
    retry_count: int = 2
    max_concurrent_workers: int = 3
    log_retention_days: int = 30


@dataclass
class AppSettings:
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    scrapers: ScraperSettings = field(default_factory=ScraperSettings)
    # log_base_dir: 일별 로그 디렉터리가 생성되는 절대 경로
    log_base_dir: str = ""


_DEFAULT_CONFIG_PATH = Path.home() / ".settlement_app" / "config.json"

# AppSettings 필드명 → 중첩 dataclass 타입 매핑.
_NESTED: dict[str, type] = {
    "db": DatabaseSettings,
    "storage": StorageSettings,
    "scrapers": ScraperSettings,
}


def _deserialize_dataclass(cls: Type[_DC], data: dict[str, Any], context: str) -> _DC:
    """
    dataclasses.fields()를 사용해 *data*로부터 *cls* 인스턴스를 생성.
    알 수 없는 키는 경고를 기록. 누락된 키는 dataclass 필드의
    default / default_factory로 폴백.
    """
    known = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data.keys()) - known
    for key in unknown:
        logger.warning("unknown config key '%s.%s' — ignored", context, key)

    # PEP 563 / `from __future__ import annotations`가 `f.type`을 문자열로 만드므로,
    # 올바른 타입 변환을 위해 get_type_hints로 실제 타입을 한 번 해석한다.
    hints = get_type_hints(cls)

    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        if f.name not in data:
            continue  # dataclass 기본값 사용
        raw_val = data[f.name]
        if hints.get(f.name) is int:
            try:
                kwargs[f.name] = int(raw_val)
            except (TypeError, ValueError):
                logger.warning(
                    "config key '%s.%s' expected int, got %r — using default",
                    context, f.name, raw_val,
                )
        else:
            kwargs[f.name] = raw_val
    return cls(**kwargs)


def load_settings(config_path: Path | None = None) -> AppSettings:
    """
    JSON 파일에서 AppSettings를 로드하며, 기본값으로 폴백.

    - 어떤 레벨에서든 누락된 키는 dataclass 기본값으로 폴백.
    - 알 수 없는 키는 stderr에 WARNING을 방출하되 예외를 발생시키지 않음.
    - TODO: keyring 또는 AES 키 파일을 통한 암호화 자격증명 로드 추가.
    """
    path = config_path or Path(os.environ.get("SETTLEMENT_APP_CONFIG", str(_DEFAULT_CONFIG_PATH)))
    if not path.exists():
        return AppSettings()

    with path.open(encoding="utf-8") as f:
        raw: dict[str, Any] = json.load(f)

    # 알 수 없는 최상위 키 경고
    top_known = {f.name for f in dataclasses.fields(AppSettings)}
    for key in set(raw.keys()) - top_known:
        logger.warning("unknown top-level config key '%s' — ignored", key)

    # 중첩 dataclass 섹션 역직렬화
    nested_kwargs: dict[str, Any] = {}
    for field_name, nested_cls in _NESTED.items():
        section = raw.get(field_name)
        if section is None:
            nested_kwargs[field_name] = nested_cls()
        elif not isinstance(section, dict):
            logger.warning(
                "config section '%s' expected a JSON object, got %s — using defaults",
                field_name, type(section).__name__,
            )
            nested_kwargs[field_name] = nested_cls()
        else:
            nested_kwargs[field_name] = _deserialize_dataclass(
                nested_cls, section, context=field_name
            )

    # 스칼라 최상위 필드 (현재는 log_base_dir만 해당)
    scalar_kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(AppSettings):
        if f.name in _NESTED:
            continue
        if f.name in raw:
            scalar_kwargs[f.name] = raw[f.name]

    return AppSettings(**nested_kwargs, **scalar_kwargs)
