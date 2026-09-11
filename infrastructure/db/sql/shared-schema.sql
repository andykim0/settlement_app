-- =============================================================================
-- 배달 정산 로컬 관리자 · PostgreSQL 스키마 — delivery_shared (개선판 v5 · prj2)
-- 단일 소스(schema_data.py)에서 자동 생성
-- 본 파일은 delivery_shared 데이터베이스에만 적재된다. (00-init.sh 참조)
-- 호환 백엔드: Spring Boot 4.0.6 / Java 25 / Spring Security 7 (stateless JWT)
-- v4→v5: 지사 장비 관리 신설 (branch_equipment + branch_equipment_photo 1:N)
-- v3→v4: 지사+관리자 통합, admin/auth_login/auth_audit/worker/key_meta 테이블 제거
--        (로그→CloudWatch, 관리자→Docker ENV, worker/key→application.yml/ENV)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- gen_random_uuid()


-- ---- app_account  (통합 계정, req=AUTH-001, group=auth) ----
-- desc : Spring Security 인증 주체 계정. 어플리케이션 코드(app_code)로 역할을 식별한다(RIDER_APP/BRANCH_WEB).
-- note : ADMIN_WEB 단일 관리자 계정은 Docker 환경변수(argon2id 해시 주입)로 분리 관리되어 본 테이블 미사용. JWT sub=id(uuid), role=app_code, tv=token_version.
CREATE TABLE app_account (
    id                             uuid NOT NULL DEFAULT gen_random_uuid(),
    app_code                       varchar(30) NOT NULL,
    username                       varchar(100) NOT NULL,
    password_hash                  varchar(255) NOT NULL,
    status                         varchar(30) NOT NULL DEFAULT 'ACTIVE',
    enabled                        boolean NOT NULL DEFAULT true,
    account_non_locked             boolean NOT NULL DEFAULT true,
    failed_login_count             integer NOT NULL DEFAULT 0,
    locked_until                   timestamptz,
    token_version                  integer NOT NULL DEFAULT 0,
    last_login_at                  timestamptz,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id),
    UNIQUE (app_code, username)
);
CREATE INDEX idx_app_account_app_code ON app_account(app_code);
CREATE INDEX idx_app_account_username ON app_account(username);
CREATE INDEX idx_app_account_deleted_at ON app_account(deleted_at);

-- ---- auth_refresh_token  (리프레시 토큰, req=AUTH-002, group=auth) ----
-- desc : JWT refresh token 저장소 겸 차단 목록. 강제 로그아웃·재발급은 revoked_at 으로 처리.
-- note : 토큰 평문은 보관하지 않고 SHA-256(또는 HMAC) 해시만 저장. 만료된 row 는 batch cleanup. Access Token 즉시 차단은 app_account.token_version+1 정책으로 처리.
CREATE TABLE auth_refresh_token (
    id                             uuid NOT NULL DEFAULT gen_random_uuid(),
    account_id                     uuid NOT NULL,
    app_code                       varchar(30) NOT NULL,
    token_hash                     varchar(255) NOT NULL,
    issued_at                      timestamptz NOT NULL DEFAULT now(),
    expires_at                     timestamptz NOT NULL,
    revoked_at                     timestamptz,
    revoke_reason                  varchar(100),
    ip_address                     inet,
    user_agent                     text,
    PRIMARY KEY (id),
    UNIQUE (token_hash)
);
CREATE INDEX idx_auth_refresh_token_account_id ON auth_refresh_token(account_id);
CREATE INDEX idx_auth_refresh_token_app_code ON auth_refresh_token(app_code);
CREATE INDEX idx_auth_refresh_token_token_hash ON auth_refresh_token(token_hash);
CREATE INDEX idx_auth_refresh_token_expires_at ON auth_refresh_token(expires_at);
CREATE INDEX idx_auth_refresh_token_revoked_at ON auth_refresh_token(revoked_at);

-- ---- branch  (지사, req=BR-001, group=org) ----
-- desc : 라이더 정산의 기준이 되는 지사 마스터. v4 부터 지사 관리자 정보를 통합 보유(1지사 = 1관리자 계정 영구 고정 정책).
-- note : account_id 는 app_account.id(app_code=BRANCH_WEB) 1:1 참조. 사업자등록번호·대표자·연락처·이메일은 가입 시 수집. 추후 부관리자가 필요해지면 별 매핑 테이블을 도입한다.
CREATE TABLE branch (
    id                             bigint NOT NULL,
    branch_code                    varchar(50) NOT NULL,
    name                           varchar(255) NOT NULL,
    account_id                     uuid NOT NULL,
    business_registration_no       varchar(100) NOT NULL,
    representative_name            varchar(100) NOT NULL,
    phone_number                   varchar(50) NOT NULL,
    email                          varchar(255),
    status                         varchar(30) NOT NULL DEFAULT 'ACTIVE',
    signed_up_at                   timestamptz NOT NULL DEFAULT now(),
    memo                           text,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id),
    UNIQUE (branch_code),
    UNIQUE (account_id)
);
CREATE INDEX idx_branch_branch_code ON branch(branch_code);
CREATE INDEX idx_branch_name ON branch(name);
CREATE INDEX idx_branch_account_id ON branch(account_id);
CREATE INDEX idx_branch_business_registration_no ON branch(business_registration_no);
CREATE INDEX idx_branch_phone_number ON branch(phone_number);
CREATE INDEX idx_branch_email ON branch(email);
CREATE INDEX idx_branch_status ON branch(status);
CREATE INDEX idx_branch_deleted_at ON branch(deleted_at);

-- ---- delivery_platform  (배달 플랫폼, req=PLT-001, group=plt) ----
-- desc : 쿠팡/배민 등 외부 배달 플랫폼 마스터.
-- note : 플랫폼 추가는 운영 화면에서. 비활성화는 is_active=false, 삭제는 deleted_at.
CREATE TABLE delivery_platform (
    id                             bigint NOT NULL,
    platform_code                  varchar(30) NOT NULL,
    name                           varchar(100) NOT NULL,
    login_url                      text,
    settlement_path                text,
    is_active                      boolean NOT NULL DEFAULT true,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id),
    UNIQUE (platform_code)
);
CREATE INDEX idx_delivery_platform_platform_code ON delivery_platform(platform_code);
CREATE INDEX idx_delivery_platform_is_active ON delivery_platform(is_active);
CREATE INDEX idx_delivery_platform_deleted_at ON delivery_platform(deleted_at);

-- ---- branch_platform_account  (지사 도메인 계정, req=PLT-002, group=plt) ----
-- desc : 지사가 보유한 플랫폼 도메인 계정(로그인 ID/PW + 다운로드 엑셀 오픈 암호). v4 부터 AAD·worker FK·키 메타 FK 제거.
-- note : ID/PW/엑셀 암호 모두 AES-256-GCM. 각 컬럼은 (ciphertext bytea, iv bytea) 쌍이며 ciphertext 끝 16바이트는 GCM 인증 태그(Cipher.doFinal 결과를 그대로 보관). IV는 매 암호화마다 SecureRandom 12바이트 신규 생성, 절대 재사용 금지. encryption_key_alias 는 ENV/AWS KMS 의 raw key 를 lookup 하는 별칭일 뿐 키 자체가 아니다. auth_target(이메일/전화)을 보고 Control PC 가 worker 분배를 결정한다.
CREATE TABLE branch_platform_account (
    id                             bigint NOT NULL,
    branch_id                      bigint NOT NULL,
    platform_id                    bigint NOT NULL,
    account_label                  varchar(100) NOT NULL,
    login_id_ciphertext            bytea NOT NULL,
    login_id_iv                    bytea NOT NULL,
    login_password_ciphertext      bytea NOT NULL,
    login_password_iv              bytea NOT NULL,
    excel_open_password_ciphertext bytea,
    excel_open_password_iv         bytea,
    encryption_key_alias           varchar(100) NOT NULL,
    auth_method                    varchar(20) NOT NULL,
    auth_target                    varchar(255),
    is_active                      boolean NOT NULL DEFAULT true,
    last_login_success_at          timestamptz,
    last_login_failed_at           timestamptz,
    memo                           text,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id),
    UNIQUE (branch_id, platform_id, account_label)
);
CREATE INDEX idx_branch_platform_account_branch_id ON branch_platform_account(branch_id);
CREATE INDEX idx_branch_platform_account_platform_id ON branch_platform_account(platform_id);
CREATE INDEX idx_branch_platform_account_account_label ON branch_platform_account(account_label);
CREATE INDEX idx_branch_platform_account_encryption_key_alias ON branch_platform_account(encryption_key_alias);
CREATE INDEX idx_branch_platform_account_auth_method ON branch_platform_account(auth_method);
CREATE INDEX idx_branch_platform_account_is_active ON branch_platform_account(is_active);
CREATE INDEX idx_branch_platform_account_deleted_at ON branch_platform_account(deleted_at);

-- ---- branch_common_charge  (지사 공통 납부, req=PAY-001, group=pay) ----
-- desc : 지사 단위로 라이더에게 공통 부과되는 항목(보험·단말기 임대료 등).
-- note : payment_cycle(DAILY/WEEKLY) 로 일/주단위 납부 정책 적용. WEEKLY 면 weekly_apply_day_of_week(1=월..7=일) 지정 필수. effective_from/to 로 시점별 단가 이력 관리.
CREATE TABLE branch_common_charge (
    id                             bigint NOT NULL,
    branch_id                      bigint NOT NULL,
    charge_code                    varchar(50) NOT NULL,
    charge_name                    varchar(255) NOT NULL,
    amount                         numeric(14,2) NOT NULL DEFAULT 0,
    payment_cycle                  varchar(10) NOT NULL DEFAULT 'DAILY',
    weekly_apply_day_of_week       smallint,
    effective_from                 date NOT NULL,
    effective_to                   date,
    is_active                      boolean NOT NULL DEFAULT true,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id)
);
CREATE INDEX idx_branch_common_charge_branch_id ON branch_common_charge(branch_id);
CREATE INDEX idx_branch_common_charge_charge_code ON branch_common_charge(charge_code);
CREATE INDEX idx_branch_common_charge_payment_cycle ON branch_common_charge(payment_cycle);
CREATE INDEX idx_branch_common_charge_effective_from ON branch_common_charge(effective_from);
CREATE INDEX idx_branch_common_charge_effective_to ON branch_common_charge(effective_to);
CREATE INDEX idx_branch_common_charge_is_active ON branch_common_charge(is_active);
CREATE INDEX idx_branch_common_charge_deleted_at ON branch_common_charge(deleted_at);

-- ---- rider_individual_charge  (라이더 개별 납부, req=PAY-002, group=pay) ----
-- desc : 라이더 개별 부과 항목(개인 대출 상환, 페널티 등). 분할 납부 계획에 속한 회차는 installment_plan_id 로 연결.
-- note : installment_plan_id 가 NOT NULL 이면 본 row 는 해당 분할 납부 계획의 회차별 차감 항목. NULL 이면 일반 일/주 단위 단발/반복 부과. rider_id 는 Aurora Rider DB 논리 참조.
CREATE TABLE rider_individual_charge (
    id                             bigint NOT NULL,
    rider_id                       bigint NOT NULL,
    branch_id                      bigint NOT NULL,
    installment_plan_id            bigint,
    charge_code                    varchar(50) NOT NULL,
    charge_name                    varchar(255) NOT NULL,
    amount                         numeric(14,2) NOT NULL DEFAULT 0,
    payment_cycle                  varchar(10) NOT NULL DEFAULT 'DAILY',
    weekly_apply_day_of_week       smallint,
    effective_from                 date NOT NULL,
    effective_to                   date,
    is_one_time                    boolean NOT NULL DEFAULT false,
    is_active                      boolean NOT NULL DEFAULT true,
    memo                           text,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id)
);
CREATE INDEX idx_rider_individual_charge_rider_id ON rider_individual_charge(rider_id);
CREATE INDEX idx_rider_individual_charge_branch_id ON rider_individual_charge(branch_id);
CREATE INDEX idx_rider_individual_charge_installment_plan_id ON rider_individual_charge(installment_plan_id);
CREATE INDEX idx_rider_individual_charge_charge_code ON rider_individual_charge(charge_code);
CREATE INDEX idx_rider_individual_charge_payment_cycle ON rider_individual_charge(payment_cycle);
CREATE INDEX idx_rider_individual_charge_effective_from ON rider_individual_charge(effective_from);
CREATE INDEX idx_rider_individual_charge_effective_to ON rider_individual_charge(effective_to);
CREATE INDEX idx_rider_individual_charge_is_active ON rider_individual_charge(is_active);
CREATE INDEX idx_rider_individual_charge_deleted_at ON rider_individual_charge(deleted_at);

-- ---- rider_installment_plan  (라이더 분할 납부 계획, req=PAY-003, group=pay) ----
-- desc : [NEW] 개별 라이더가 일정 금액을 일정 기간에 걸쳐 분할 납부하는 계획. v4 에서 승인자 컬럼 제거(지사 1계정 정책).
-- note : 정산 실행 시 ACTIVE 상태인 분할 계획을 조회하여 회차당 금액을 라이더 정산액에서 차감. paid_count/paid_amount 는 정산 완료 트랜잭션에서 원자적 +1/+amount. rider_payment_deferral 기간 동안 회차는 진행 안 되고 end_date 가 자동 연장됨(애플리케이션 정책).
CREATE TABLE rider_installment_plan (
    id                             bigint NOT NULL,
    rider_id                       bigint NOT NULL,
    branch_id                      bigint NOT NULL,
    plan_code                      varchar(50) NOT NULL,
    plan_name                      varchar(255) NOT NULL,
    total_amount                   numeric(14,2) NOT NULL,
    installment_count              integer NOT NULL,
    installment_amount             numeric(14,2) NOT NULL,
    payment_cycle                  varchar(10) NOT NULL DEFAULT 'DAILY',
    weekly_apply_day_of_week       smallint,
    start_date                     date NOT NULL,
    end_date                       date NOT NULL,
    paid_count                     integer NOT NULL DEFAULT 0,
    paid_amount                    numeric(14,2) NOT NULL DEFAULT 0,
    status                         varchar(30) NOT NULL DEFAULT 'ACTIVE',
    memo                           text,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id),
    UNIQUE (plan_code)
);
CREATE INDEX idx_rider_installment_plan_rider_id ON rider_installment_plan(rider_id);
CREATE INDEX idx_rider_installment_plan_branch_id ON rider_installment_plan(branch_id);
CREATE INDEX idx_rider_installment_plan_plan_code ON rider_installment_plan(plan_code);
CREATE INDEX idx_rider_installment_plan_payment_cycle ON rider_installment_plan(payment_cycle);
CREATE INDEX idx_rider_installment_plan_start_date ON rider_installment_plan(start_date);
CREATE INDEX idx_rider_installment_plan_end_date ON rider_installment_plan(end_date);
CREATE INDEX idx_rider_installment_plan_status ON rider_installment_plan(status);
CREATE INDEX idx_rider_installment_plan_deleted_at ON rider_installment_plan(deleted_at);

-- ---- rider_payment_deferral  (라이더 납부 연기, req=PAY-004, group=pay) ----
-- desc : [NEW] 라이더가 부득이한 사정으로 일정 기간 쉴 때 공통/개별/분할 회차 일체를 정지. v4 에서 승인자 컬럼 제거.
-- note : 정산 배치는 defer_from ≤ 정산일 ≤ COALESCE(defer_to, actual_resumed_at, infinity) 인 라이더의 일체 부과를 스킵. 복귀 처리는 actual_resumed_at 기록 + status=RESUMED. defer_to=NULL 이면 무기한 연기(복귀까지). 분할 계획 end_date 는 연기 일수만큼 자동 연장한다.
CREATE TABLE rider_payment_deferral (
    id                             bigint NOT NULL,
    rider_id                       bigint NOT NULL,
    branch_id                      bigint NOT NULL,
    defer_from                     date NOT NULL,
    defer_to                       date,
    actual_resumed_at              date,
    reason                         varchar(255),
    status                         varchar(30) NOT NULL DEFAULT 'ACTIVE',
    memo                           text,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id)
);
CREATE INDEX idx_rider_payment_deferral_rider_id ON rider_payment_deferral(rider_id);
CREATE INDEX idx_rider_payment_deferral_branch_id ON rider_payment_deferral(branch_id);
CREATE INDEX idx_rider_payment_deferral_defer_from ON rider_payment_deferral(defer_from);
CREATE INDEX idx_rider_payment_deferral_defer_to ON rider_payment_deferral(defer_to);
CREATE INDEX idx_rider_payment_deferral_actual_resumed_at ON rider_payment_deferral(actual_resumed_at);
CREATE INDEX idx_rider_payment_deferral_status ON rider_payment_deferral(status);
CREATE INDEX idx_rider_payment_deferral_deleted_at ON rider_payment_deferral(deleted_at);

-- ---- branch_equipment  (지사 장비, req=EQ-001, group=eq) ----
-- desc : 지사가 보유·관리하는 운영 장비(헬멧·바이크·무전기·재킷 등) 마스터.
-- note : 한 장비 row 당 복수의 사진(branch_equipment_photo)을 가진다. assigned_rider_id 는 현재 사용 중인 라이더의 논리 참조(외부 DB). 장비 폐기는 status=DISPOSED + deleted_at 로 처리.
CREATE TABLE branch_equipment (
    id                             bigint NOT NULL,
    branch_id                      bigint NOT NULL,
    equipment_code                 varchar(50) NOT NULL,
    equipment_name                 varchar(255) NOT NULL,
    equipment_type                 varchar(50) NOT NULL,
    serial_number                  varchar(100),
    status                         varchar(30) NOT NULL DEFAULT 'IN_USE',
    assigned_rider_id              bigint,
    purchase_date                  date,
    purchase_price                 numeric(14,2),
    memo                           text,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id),
    UNIQUE (branch_id, equipment_code)
);
CREATE INDEX idx_branch_equipment_branch_id ON branch_equipment(branch_id);
CREATE INDEX idx_branch_equipment_equipment_code ON branch_equipment(equipment_code);
CREATE INDEX idx_branch_equipment_equipment_name ON branch_equipment(equipment_name);
CREATE INDEX idx_branch_equipment_equipment_type ON branch_equipment(equipment_type);
CREATE INDEX idx_branch_equipment_serial_number ON branch_equipment(serial_number);
CREATE INDEX idx_branch_equipment_status ON branch_equipment(status);
CREATE INDEX idx_branch_equipment_assigned_rider_id ON branch_equipment(assigned_rider_id);
CREATE INDEX idx_branch_equipment_deleted_at ON branch_equipment(deleted_at);

-- ---- branch_equipment_photo  (지사 장비 사진, req=EQ-002, group=eq) ----
-- desc : 장비별로 보관하는 상태 캡쳐 사진. 최초 등록 사진과 점검/파손 시점 사진을 비교해 훼손 여부를 판단하는 용도.
-- note : 한 장비당 복수 사진(1:N). photo_type 으로 INITIAL(최초 등록), INSPECTION(정기 점검), DAMAGE(파손 확인), REPAIR(수리 후) 단계를 구분해 비교가 쉽도록 한다. storage_type=LOCAL 이면 file_path 가 로컬/NAS 경로, S3 면 s3_bucket/s3_key 사용(file_path 는 s3:// URL 보관).
CREATE TABLE branch_equipment_photo (
    id                             bigint NOT NULL,
    equipment_id                   bigint NOT NULL,
    photo_type                     varchar(30) NOT NULL DEFAULT 'INITIAL',
    taken_at                       timestamptz NOT NULL,
    file_name                      varchar(255) NOT NULL,
    file_path                      text NOT NULL,
    storage_type                   varchar(20) NOT NULL DEFAULT 'LOCAL',
    s3_bucket                      varchar(255),
    s3_key                         text,
    file_size_bytes                bigint,
    mime_type                      varchar(50),
    description                    text,
    created_at                     timestamptz NOT NULL DEFAULT now(),
    updated_at                     timestamptz NOT NULL DEFAULT now(),
    deleted_at                     timestamptz,
    PRIMARY KEY (id)
);
CREATE INDEX idx_branch_equipment_photo_equipment_id ON branch_equipment_photo(equipment_id);
CREATE INDEX idx_branch_equipment_photo_photo_type ON branch_equipment_photo(photo_type);
CREATE INDEX idx_branch_equipment_photo_taken_at ON branch_equipment_photo(taken_at);
CREATE INDEX idx_branch_equipment_photo_storage_type ON branch_equipment_photo(storage_type);
CREATE INDEX idx_branch_equipment_photo_deleted_at ON branch_equipment_photo(deleted_at);


-- =============================================================================
-- FK 제약 (delivery_shared 내부). 교차 DB 참조(rider_id 등)는 FK 없이 논리 참조만.
-- =============================================================================
ALTER TABLE branch ADD CONSTRAINT fk_branch_account_id FOREIGN KEY (account_id) REFERENCES app_account(id);
ALTER TABLE auth_refresh_token ADD CONSTRAINT fk_auth_refresh_token_account_id FOREIGN KEY (account_id) REFERENCES app_account(id);
ALTER TABLE branch_platform_account ADD CONSTRAINT fk_branch_platform_account_branch_id FOREIGN KEY (branch_id) REFERENCES branch(id);
ALTER TABLE branch_platform_account ADD CONSTRAINT fk_branch_platform_account_platform_id FOREIGN KEY (platform_id) REFERENCES delivery_platform(id);
ALTER TABLE branch_common_charge ADD CONSTRAINT fk_branch_common_charge_branch_id FOREIGN KEY (branch_id) REFERENCES branch(id);
ALTER TABLE rider_individual_charge ADD CONSTRAINT fk_rider_individual_charge_branch_id FOREIGN KEY (branch_id) REFERENCES branch(id);
ALTER TABLE rider_individual_charge ADD CONSTRAINT fk_rider_individual_charge_installment_plan_id FOREIGN KEY (installment_plan_id) REFERENCES rider_installment_plan(id);
ALTER TABLE rider_installment_plan ADD CONSTRAINT fk_rider_installment_plan_branch_id FOREIGN KEY (branch_id) REFERENCES branch(id);
ALTER TABLE rider_payment_deferral ADD CONSTRAINT fk_rider_payment_deferral_branch_id FOREIGN KEY (branch_id) REFERENCES branch(id);
ALTER TABLE branch_equipment ADD CONSTRAINT fk_branch_equipment_branch_id FOREIGN KEY (branch_id) REFERENCES branch(id);
ALTER TABLE branch_equipment_photo ADD CONSTRAINT fk_branch_equipment_photo_equipment_id FOREIGN KEY (equipment_id) REFERENCES branch_equipment(id);


-- =============================================================================
-- 운영 정책 (코멘트)
-- =============================================================================
-- [Soft Delete 정책]
--   모든 운영 데이터 테이블에 deleted_at(timestamptz) 컬럼을 둔다.
--   * NULL = 정상(노출 대상), NOT NULL = 논리 삭제(노출 제외)
--   * 일반 조회는 항상 WHERE deleted_at IS NULL
--   * Hibernate/JPA의 @SQLRestriction("deleted_at IS NULL") 또는 @Filter로 강제 권장
--   * 실제 row 삭제는 운영팀 전용 데이터 정리 도구에서만 허용
--   * 본 정책으로 인해 'delete' 화면 액션은 SQL DELETE 가 아니라 UPDATE deleted_at = now() 로 구현

-- [JWT 인증·인가 정책]
--   1) 어플리케이션은 application.yml 에 정적 등록한다(RIDER_APP / BRANCH_WEB).
--   2) ADMIN_WEB(관리자 root) 계정은 Docker 환경변수로 분리 관리, app_account 테이블 미사용.
--      ADMIN_USERNAME, ADMIN_PASSWORD_HASH(argon2id) 형태로 주입. 평문 ENV 금지.
--      운영: AWS Secrets Manager + ECS Task Role 로 부팅 시 fetch 권장.
--   3) 관리자 웹 IP/장비 제한: ALB SG 사무실 IP allow + mTLS 클라이언트 인증서 조합.
--      강화 시 AWS Verified Access(IAM Identity Center + 디바이스 신뢰).
--   4) JWT 클레임: sub=app_account.id, role=app_account.app_code, tv=app_account.token_version
--   5) Access Token 검증: HS256/RS256 서명 + tv == app_account.token_version (DB 1회 조회 또는 캐시)
--   6) Access Token 즉시 차단: app_account.token_version += 1 (모든 기존 토큰 일괄 무효화)
--   7) Refresh Token 차단: auth_refresh_token.revoked_at 설정
--   8) 어플 ↔ 사용자 유형 매핑 강제: 로그인 시 요청 app_code 와 app_account.app_code 가 다르면 거부

-- [로그·감사 정책]
--   - 로그인 시도 기록·감사 로그는 DB 미보관. Spring Boot Actuator + Logback CloudWatch Appender
--     를 통해 CloudWatch Logs 로 구조화 JSON 전송.
--   - 실패 누적 경보는 CloudWatch Metric Filter + Alarm + SNS.
--   - 잠금 상태(failed_login_count / locked_until)는 트랜잭션 일관성이 필요하므로 app_account 에 유지.
--   - 결제·정산 실행 등 '돈에 직접 영향 주는' 액션은 별 도메인 원장 테이블(settlement_run/pg_payment 등)에 저장.

-- [암호화 규약 (AES-256-GCM)]
--   - 대상 컬럼 쌍: (login_id_ciphertext, login_id_iv), (login_password_ciphertext, login_password_iv),
--     (excel_open_password_ciphertext, excel_open_password_iv), (bank_account_ciphertext, bank_account_iv).
--   - ciphertext 끝 16바이트 = GCM 인증 태그(Cipher.doFinal 결과 그대로 보관).
--   - IV(nonce) 는 매 암호화마다 SecureRandom 12바이트 신규 생성. 절대 재사용 금지(같은 키+같은 IV → 평문 노출).
--   - 키는 DB 미보관. branch_platform_account.encryption_key_alias 가 별칭이며,
--     실 raw key 는 환경변수(현재) 또는 AWS KMS(향후) 에서 lookup. 키 로테이션은 새 alias 발급으로 처리.

-- [Worker 관리 정책]
--   - settlement_worker 테이블 없음. Worker 디바이스는 인프라 리소스.
--   - Control PC 의 application.yml 에 worker 목록·지원 플랫폼·테더링 폰·OTP 메일을 정의.
--   - 정산 시 dispatch 는 branch_platform_account.auth_target(이메일/전화) 을 보고 Control PC 가 결정.
--     SMS_OTP 면 해당 번호 테더링 worker, EMAIL_OTP 면 해당 메일 등록 worker.

-- [납부 정책]
--   - payment_cycle 컬럼이 DAILY 또는 WEEKLY 값을 가진다.
--   - WEEKLY 인 경우 weekly_apply_day_of_week (1=월 .. 7=일) 가 정산일 요일과 일치할 때만 부과.
--   - rider_payment_deferral 의 ACTIVE row 가 정산일을 포함하면 해당 라이더의 모든 부과/회차 진행을 스킵.
--   - rider_installment_plan 회차는 정산 완료 트랜잭션에서 paid_count/paid_amount 를 +1/+amount 한다.
--     paid_count == installment_count 이면 status=COMPLETED 로 전환.
--   - 연기 발생으로 회차가 스킵된 경우 rider_installment_plan.end_date 를 연기 일수만큼 자동 연장한다(애플리케이션 책임).

-- [장비 관리 정책]
--   - 지사 운영 장비(헬멧·바이크·무전기·재킷 등)는 branch_equipment 에 1 row 씩 등록.
--   - 장비별로 복수의 상태 캡쳐 사진을 branch_equipment_photo 에 1:N 으로 보관.
--   - photo_type 으로 INITIAL(최초 등록) / INSPECTION(정기 점검) / DAMAGE(파손 확인) / REPAIR(수리 후) 단계 구분.
--     비교 화면은 같은 equipment_id 의 INITIAL 과 최신 INSPECTION/DAMAGE 사진을 짝지어 표시.
--   - 사진 바이너리는 DB 미보관. storage_type=LOCAL 이면 file_path(로컬/NAS), S3 면 s3_bucket+s3_key.
--   - 장비 폐기는 status=DISPOSED + deleted_at = now(). 폐기 장비의 사진은 audit 목적으로 같이 deleted_at 처리(노출 제외).
