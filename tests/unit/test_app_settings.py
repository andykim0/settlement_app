# -*- coding: utf-8 -*-
"""
app_settings.py의 load_settings()에 대한 단위 테스트.

tmp_path를 사용하므로 실제 ~/.settlement_app/config.json 파일이 필요 없음.
"""
from __future__ import annotations

import json
import logging

import pytest

from settlement_app.infrastructure.settings.app_settings import (
    AppSettings,
    DatabaseSettings,
    ScraperSettings,
    StorageSettings,
    load_settings,
)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _write_config(tmp_path, data: dict) -> "pathlib.Path":
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------

def test_missing_file_returns_defaults(tmp_path):
    """존재하지 않는 경로 → 모든 기본값을 가진 AppSettings()와 동일."""
    result = load_settings(config_path=tmp_path / "no_such_file.json")
    assert result == AppSettings()


def test_complete_json_deserializes_all_sections(tmp_path):
    """세 개의 중첩 섹션 모두 예상 값으로 역직렬화."""
    config = {
        "db": {
            "host": "db.internal",
            "port": 5433,
            "shared_database": "prod_shared",
            "rider_database": "prod_rider",
            "sslmode": "require",
        },
        "storage": {
            "local_excel_dir": "/data/excels",
            "s3_bucket": "my-bucket",
        },
        "scrapers": {
            "coupang_id": "cp_user",
            "baemin_id": "bm_user",
            "sms_server_port": 9999,
            "max_concurrent_workers": 5,
        },
        "log_base_dir": "/var/log/settlement",
    }
    p = _write_config(tmp_path, config)
    s = load_settings(config_path=p)

    assert s.db.host == "db.internal"
    assert s.db.port == 5433
    assert s.db.shared_database == "prod_shared"
    assert s.db.rider_database == "prod_rider"
    assert s.db.sslmode == "require"

    assert s.storage.local_excel_dir == "/data/excels"
    assert s.storage.s3_bucket == "my-bucket"

    assert s.scrapers.coupang_id == "cp_user"
    assert s.scrapers.baemin_id == "bm_user"
    assert s.scrapers.sms_server_port == 9999
    assert s.scrapers.max_concurrent_workers == 5

    assert s.log_base_dir == "/var/log/settlement"


def test_partial_json_only_scrapers_leaves_other_sections_as_defaults(tmp_path):
    """'scrapers' 블록만 존재 → db와 storage는 기본 인스턴스."""
    config = {
        "scrapers": {"coupang_id": "ridestar211p", "baemin_id": "ridestar1"},
    }
    p = _write_config(tmp_path, config)
    s = load_settings(config_path=p)

    # scrapers 값이 설정되어 있는지 확인
    assert s.scrapers.coupang_id == "ridestar211p"
    assert s.scrapers.baemin_id == "ridestar1"

    # 나머지 섹션은 기본값인지 확인
    assert s.db == DatabaseSettings()
    assert s.storage == StorageSettings()
    assert s.log_base_dir == ""


def test_unknown_top_level_key_warns_but_does_not_fail(tmp_path, caplog):
    """알 수 없는 최상위 키는 WARNING을 기록하지만 로딩은 성공."""
    config = {
        "scrapers": {"coupang_id": "x"},
        "future_feature_key": "somevalue",
    }
    p = _write_config(tmp_path, config)
    with caplog.at_level(logging.WARNING, logger="settlement_app.infrastructure.settings.app_settings"):
        s = load_settings(config_path=p)

    assert s.scrapers.coupang_id == "x"  # 유효한 키는 정상적으로 로드됨
    assert any(
        r.levelno == logging.WARNING and "future_feature_key" in r.getMessage()
        for r in caplog.records
    )


def test_unknown_nested_key_warns_but_does_not_fail(tmp_path, caplog):
    """중첩 섹션 내 알 수 없는 키는 WARNING을 기록하고 나머지 섹션은 정상 로드."""
    config = {
        "scrapers": {
            "coupang_id": "ridestar211p",
            "unknown_field": "should_warn",
        },
    }
    p = _write_config(tmp_path, config)
    with caplog.at_level(logging.WARNING, logger="settlement_app.infrastructure.settings.app_settings"):
        s = load_settings(config_path=p)

    assert s.scrapers.coupang_id == "ridestar211p"
    assert any(
        r.levelno == logging.WARNING and "unknown_field" in r.getMessage()
        for r in caplog.records
    )


def test_empty_json_object_returns_all_defaults(tmp_path):
    """빈 JSON {}은 AppSettings()와 동일한 결과를 생성해야 함."""
    p = _write_config(tmp_path, {})
    s = load_settings(config_path=p)
    assert s == AppSettings()


def test_log_base_dir_and_db_host_round_trip(tmp_path):
    """스칼라 최상위 필드와 db 필드가 라운드트립을 정상적으로 통과."""
    config = {
        "log_base_dir": "/tmp/logs",
        "db": {"host": "192.168.1.5"},
    }
    p = _write_config(tmp_path, config)
    s = load_settings(config_path=p)
    assert s.log_base_dir == "/tmp/logs"
    assert s.db.host == "192.168.1.5"
    # 나머지 db 필드는 기본값인지 확인
    assert s.db.port == 5432
    assert s.db.shared_database == "delivery_shared"
    assert s.db.rider_database == "delivery_rider"
