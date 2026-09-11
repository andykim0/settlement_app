-- =============================================================================
-- 배달 정산 로컬 관리자 · PostgreSQL 스키마 — delivery_rider (개선판 v5 · prj2)
-- 단일 소스(schema_data.py)에서 자동 생성
-- 본 파일은 delivery_rider 데이터베이스에만 적재된다. (00-init.sh 참조)
-- 호환 백엔드: Spring Boot 4.0.6 / Java 25 / Spring Security 7 (stateless JWT)
--
-- 교차 DB 참조: branch_id, account_id 는 delivery_shared 의 branch / app_account
-- 를 가리키는 논리 참조이며 FK 제약은 만들지 않는다(다른 DB).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- (delivery_shared 와의 패리티 유지용)


-- ---- rider  (라이더, req=RD-001, group=rd) ----
-- desc : 실제 배달을 수행하는 라이더 본체. Aurora Rider 전용 DB.
-- note : Flutter 앱 가입 시 app_account(RIDER_APP) row 생성 + 본 테이블 row 생성. app_account.id 는 외부 DB 논리 참조이므로 FK 제약 없음.
CREATE TABLE rider (
    id                             bigint NOT NULL,
    account_id                     uuid NOT NULL,
    rider_code                     varchar(50) NOT NULL,
    real_name                      varchar(100) NOT NULL,
    phone_number                   varchar(50),
    bank_name                      varchar(50),
    bank_account_ciphertext        bytea,
    bank_account_iv                bytea,
    status                         varchar(30) NOT NULL DEFAULT 'ACTIVE',
    joined_at                      date,
    left_at                        date,
    memo                           text,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id),
    UNIQUE (rider_code)
);
CREATE INDEX idx_rider_account_id ON rider(account_id);
CREATE INDEX idx_rider_rider_code ON rider(rider_code);
CREATE INDEX idx_rider_real_name ON rider(real_name);
CREATE INDEX idx_rider_phone_number ON rider(phone_number);
CREATE INDEX idx_rider_status ON rider(status);
CREATE INDEX idx_rider_deleted_at ON rider(deleted_at);

-- ---- branch_rider_affiliation  (지사-라이더 소속여부, req=RD-002, group=rd) ----
-- desc : 지사-라이더 M:N 소속 매핑. 라이더가 여러 지사에 동시 소속 가능, 그 중 1건이 메인.
-- note : branch_id 는 Aurora Shared 논리 참조. is_main=true 는 라이더당 최대 1건(partial unique index + AND deleted_at IS NULL).
CREATE TABLE branch_rider_affiliation (
    id                             bigint NOT NULL,
    branch_id                      bigint NOT NULL,
    rider_id                       bigint NOT NULL,
    is_main                        boolean NOT NULL DEFAULT false,
    effective_from                 date,
    effective_to                   date,
    contract_type                  varchar(30),
    memo                           text,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id),
    UNIQUE (branch_id, rider_id)
);
CREATE INDEX idx_branch_rider_affiliation_branch_id ON branch_rider_affiliation(branch_id);
CREATE INDEX idx_branch_rider_affiliation_rider_id ON branch_rider_affiliation(rider_id);
CREATE INDEX idx_branch_rider_affiliation_is_main ON branch_rider_affiliation(is_main);
CREATE INDEX idx_branch_rider_affiliation_deleted_at ON branch_rider_affiliation(deleted_at);
-- 라이더당 메인 소속 1건 제한 (소프트 삭제 제외)
CREATE UNIQUE INDEX uq_brm_main_per_rider ON branch_rider_affiliation(rider_id) WHERE is_main = true AND deleted_at IS NULL;


-- =============================================================================
-- FK 제약 (delivery_rider 내부). branch_id 는 교차 DB 참조이므로 FK 없음.
-- =============================================================================
ALTER TABLE branch_rider_affiliation ADD CONSTRAINT fk_branch_rider_affiliation_rider_id FOREIGN KEY (rider_id) REFERENCES rider(id);
