# REVIEW.md — 배달 정산 로컬 관리자

작업 중인 문서. 파일 경로 참조는 원본 프로토타입이 아니라 SPLIT 프로젝트의
`src/settlement_app/` 하위를 가리킨다.

---

## Docker 스택

### 서비스

| 서비스    | 이미지          | 포트  | 용도                                       |
|-----------|-----------------|-------|--------------------------------------------|
| postgres  | postgres:16     | 5432  | `delivery_shared` + `delivery_rider` 호스팅 |
| adminer   | adminer:latest  | 8080  | Postgres 웹 UI                             |

> v5 스키마(13 테이블)는 모두 PostgreSQL이며 ERD에 DynamoDB 항목이 없다.
> DynamoDB는 운영 도메인 저장소가 아니라 **정산 결과 송신 다운스트림 원장**
> (`WIRING.md`의 send 흐름, `AppSettings.storage.dynamodb_table`)으로
> 후속 도입 예정이다. 운영/감사/실행 상태는 Postgres 또는 메모리에 둔다.

### Postgres — 단일 클러스터 위의 두 데이터베이스

AWS Aurora 타깃 형상을 그대로 반영. 스키마 위치:
- `infrastructure/db/sql/shared-schema.sql` — `delivery_shared` (인증, 조직, 플랫폼 계정, 수수료)
- `infrastructure/db/sql/rider-schema.sql` — `delivery_rider` (rider, branch_rider_affiliation)

초기화 흐름(컨테이너 최초 기동 또는 `down -v` 이후 실행):
1. postgres 엔트리포인트가 `POSTGRES_DB=delivery_shared`를 생성
2. `00-init.sh` (`/docker-entrypoint-initdb.d/` 내):
   - `CREATE DATABASE delivery_rider`
   - `shared-schema.sql`을 `delivery_shared`에 적재
   - `rider-schema.sql`을 `delivery_rider`에 적재

개발 중 스키마 변경을 재적용하려면:
```bash
docker compose down -v && docker compose up -d
```

### v5 스키마 개요 (13 테이블)

ERD 출처: `Downloads/ERDv2/ERD_개선판2.html`. 시니어 설계 문서에 적힌 "기준 / 호환 백엔드: Spring Boot 4.0.6 / Java 25 / Spring Security 7" 는 **향후 Java 서비스가 추가될 경우의 호환성 제약**을 의미한다. 본 프로젝트는 현재 Python (PySide6) 단일 코드베이스이며, Java 백엔드는 존재하지 않는다. Python 매니저가 두 DB에 직접 psycopg 풀로 접속한다.

| 그룹     | DB                | 테이블 |
|----------|-------------------|--------|
| 인증     | `delivery_shared` | `app_account`, `auth_refresh_token` |
| 조직     | `delivery_shared` | `branch` |
| 플랫폼   | `delivery_shared` | `delivery_platform`, `branch_platform_account` |
| 납부     | `delivery_shared` | `branch_common_charge`, `rider_individual_charge`, `rider_installment_plan`, `rider_payment_deferral` |
| 장비     | `delivery_shared` | `branch_equipment`, `branch_equipment_photo` |
| 라이더   | `delivery_rider`  | `rider`, `branch_rider_affiliation` |

**핵심 규약**

- **소프트 삭제**: 모든 운영 테이블에 `deleted_at timestamptz`. 조회는 항상 `WHERE deleted_at IS NULL`. 삭제 액션은 SQL DELETE 가 아니라 `UPDATE deleted_at = now()`.
- **금액**: `numeric(14,2)`. Python에서는 `Decimal` 로 매핑, float 금지.
- **AES-256-GCM 페어**: `(ciphertext bytea, iv bytea)` 컬럼 쌍. 대상은 `branch_platform_account.{login_id, login_password, excel_open_password}` 와 `rider.bank_account`. IV는 매 암호화마다 SecureRandom 12바이트 신규, 절대 재사용 금지. 키는 DB 미보관 — `branch_platform_account.encryption_key_alias` 가 ENV/AWS KMS 의 raw key 별칭이며 alias 단위로 lookup·로테이션.
- **JWT 인가**: `app_account.app_code ∈ {RIDER_APP, BRANCH_WEB}`. `ADMIN_WEB` 은 Docker ENV(`ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` argon2id) 로만 주입하고 DB 미사용. JWT 클레임: `sub=id`, `role=app_code`, `tv=token_version`. 액세스 토큰 즉시 차단 = `token_version += 1`. 리프레시 차단 = `auth_refresh_token.revoked_at`. 요청 `app_code` 와 저장된 `app_code` 가 다르면 로그인 거부.
- **로그/감사**: DB 미보관. Spring Boot Actuator + Logback CloudWatch Appender 로 CloudWatch Logs 전송. 잠금 상태(`failed_login_count`, `locked_until`)만 트랜잭션 일관성 때문에 `app_account` 에 유지.
- **교차 DB 참조**: `delivery_shared` ↔ `delivery_rider` 사이의 `rider_id`/`branch_id`/`account_id` 는 **논리 참조** 이며 FK 제약 없음. 코드 레벨 무결성으로 보장.
- **납부 주기**: `payment_cycle ∈ {DAILY, WEEKLY}`. WEEKLY 면 `weekly_apply_day_of_week`(1=월..7=일) 와 정산일 요일이 일치할 때만 부과.
- **분할 납부 (`rider_installment_plan`)**: 정산 완료 트랜잭션에서 `paid_count`/`paid_amount` 를 원자적 +1/+amount. `paid_count == installment_count` 면 `status=COMPLETED`. 회차 row 는 `rider_individual_charge.installment_plan_id` 로 연결.
- **납부 연기 (`rider_payment_deferral`)**: ACTIVE row 가 `defer_from ≤ 정산일 ≤ COALESCE(defer_to, actual_resumed_at, infinity)` 를 만족하면 해당 라이더의 일체 부과/회차를 스킵. 분할 계획 `end_date` 는 연기 일수만큼 자동 연장(애플리케이션 책임).
- **장비 + 사진**: `branch_equipment` 1:N `branch_equipment_photo`. `photo_type ∈ {INITIAL, INSPECTION, DAMAGE, REPAIR}` 로 비교 짝짓기(같은 `equipment_id` 의 INITIAL 과 최신 INSPECTION/DAMAGE 짝지어 표시). 바이너리는 DB 미보관 — `storage_type=LOCAL`(file_path) 또는 `S3`(s3_bucket+s3_key, file_path=s3:// URL). 폐기는 `status=DISPOSED` + `deleted_at`, 사진도 같이 `deleted_at`.

DynamoDB는 위 13 테이블 어디에도 등장하지 않는다 — 정산 결과 송신 다운스트림 원장으로만 도입 예정(상단 박스 참조).

### 기동 / 종료

```bash
docker compose up -d                 # start all services
docker compose down                  # stop, keep data
docker compose down -v               # stop AND wipe volumes (replays init)
```

### 기본 인증 정보 (개발 전용)

- Postgres: user=`postgres`, password=`dev`
- 두 값 모두 로컬 편의를 위해 `docker-compose.yml`에 리터럴로 들어 있다.
- **운영 환경:** 실행 전에 `SETTLEMENT_DB_PASSWORD` 환경 변수를 설정한다.
  앱이 읽을 환경 변수 이름은 `AppSettings.db.password_env_var`로 지정한다.
  비밀번호는 절대 소스나 `config.json`에 저장하지 않는다.
- **AWS 전환:** `db.host`를 Aurora 클러스터 엔드포인트로 바꾸고,
  `db.sslmode`를 `prefer` → `require` (또는 `verify-full`)로 변경한다. 코드 경로는 동일.

### 관리자 UI

- **Adminer** (Postgres): http://localhost:8080
  - Server: `postgres` · User: `postgres` · Password: `dev`
  - Database: `delivery_shared` 또는 `delivery_rider`

### 커넥션 계층 (`infrastructure/db/postgres.py`)

`get_pool(settings, database)`는 DB별 `psycopg_pool.ConnectionPool`을 반환한다.
리포지토리는 반드시 이 경로를 거쳐야 하며, `psycopg.connect()`를 직접 호출하면 안 된다.
동일한 코드가 로컬 Docker와 AWS Aurora를 모두 타깃으로 한다 — 설정만 바뀐다.

### 헬스 체크

```bash
python scripts/check_services.py
```

`delivery_shared`와 `delivery_rider`가 모두 응답하면 0으로 종료한다.
`db` extra가 필요하다:

```bash
pip install -e ".[db]"
```

---

## 횡단 관심사

### 테마 (`presentation/theme.py`)

**현재 상태**
COLOR 딕셔너리와 GLOBAL_QSS는 모듈 레벨 상수이며, 단일 테마 앱에는 적절하다.
구조상 문제는 없음.

**핵심 이슈**
- 다크 모드 / 고대비 변형이 없음. 차단 요소는 아니지만 계획 가치는 있음.
- 폰트 패밀리 문자열에 "Malgun Gothic" 외 Windows 한국어 폰트 폴백이 없음 —
  "Segoe UI"는 선택 폰트팩이 설치되지 않은 구형 Windows 10에서 한국어 렌더링이
  열악할 수 있음.

**리팩터 계획**
- 일단 현 상태 유지.
- 다크 모드가 필요해지면 `ThemeConfig` 데이터클래스를 도입하고, 기동 시점에
  이로부터 `GLOBAL_QSS`를 계산한다.

---

### 위젯 (`presentation/widgets/`)

**현재 상태**
badge.py, buttons.py, cards.py, table.py, misc.py로 분리. 각 위젯은 깔끔하고
상태 비저장.

**핵심 이슈**
- `presentation/widgets/cards.py:49` — `StatCard`가 라벨/값을 생성자에서만
  설정함. `update_value()` 메서드가 없어 데이터를 갱신하려면 위젯 전체를
  다시 만들어야 함. 실제 데이터가 들어오면 문제가 된다.
- `presentation/widgets/table.py:53` — `FlatTable.add_row()`가 원시 문자열을
  받음. 타입드 DTO 경로가 아직 없음. `populate_from_dto()`는 TODO로 스텁됨.
- `presentation/widgets/misc.py:20` — `progress_cell()`이 호출될 때마다
  (테이블 갱신마다) 새 `QProgressBar`를 만든다. 폴링 사이클마다 수백 개
  위젯을 생성/파괴하므로 큰 테이블에서 부담이 크다.

**리팩터 계획**
- `StatCard.update(value, foot)` 슬롯 추가. 프레젠터에서 타이머 틱마다 호출.
- `FlatTable.populate_from_dto(rows)` 추가. `clear_rows()` 후 각 DTO에 대해
  `add_row()` 호출. `row_factory: Callable[[T], list]` 파라미터를 받게 함.
- 대용량 테이블(특히 모니터링 로그 테이블)에는 델리게이트 기반
  QAbstractTableModel을 검토 — QTableWidget은 ~500행을 넘으면 확장성이 없다.

---

### 다이얼로그 (`presentation/dialogs/`)

**현재 상태**
다이얼로그/오버레이 7개가 5개 파일에 분산. 모두 `_BaseDialog`를 상속.
현재는 모두 정적 하드코딩 행을 표시.

**핵심 이슈**
- `dialogs/run_all_confirm.py:38` — 단계 목록이 하드코딩. 실제 실행 파이프라인이
  바뀌면 이 다이얼로그는 사용자에게 조용히 거짓을 보여 준다.
- `dialogs/rider_mapping.py:27` — 행이 정적. "PostgreSQL 업데이트" 버튼이
  `self.accept()`만 호출해 아무 일도 안 함. 서비스 호출이 연결되어 있지 않다.
- `dialogs/settlement_mapping.py:29` — 금액 컬럼("기본 지급", "Net" 등)이
  원시 정수 문자열. 계산 및 검증 로직은 다이얼로그에 두지 말 것 —
  settlement-logic-specialist에 위임.
- `dialogs/force_complete.py:39` — "완료 처리" accept 핸들러가 어떤 유스케이스도
  호출하지 않음. 부수 효과가 사라진다.
- `dialogs/send_complete.py:77` — 진행 오버레이가 62% 값을 하드코딩하고
  시그널 배선이 없음.

**리팩터 계획**
- 다이얼로그를 생성자 주입으로 유스케이스에 연결한다(전역 조회가 아니라 서비스나
  유스케이스 인스턴스를 다이얼로그 생성자에 전달).
- `RunAllConfirmDialog` → `RunAllUseCase.describe_steps()` 호출.
- `RiderMappingDialog` → 생성자에서 `RiderMappingResult` DTO를 받아 표시;
  "업데이트" 버튼은 주입된 `on_confirm: Callable`을 호출.
- 진행 오버레이는 `QThread` 또는 `Signal` 객체를 받아 `ScraperWorker`의
  `progress_updated` 시그널로 `QProgressBar`를 갱신해야 한다.

---

## 페이지 1: 대시보드

**현재 상태**
정적 하드코딩 통계 카드와 테이블 두 개. "전체 프로세스 실행"이
`RunAllConfirmDialog`를 띄우지만 accept만 될 뿐 아무 것도 트리거하지 않음.

**핵심 이슈**
- `pages/dashboard_page.py:33` — `StatCard` 네 개의 값이 하드코딩 문자열.
  `DashboardService.get_stats()` → `DashboardStatsDTO`가 필요.
- `pages/dashboard_page.py:50` — "최근 작업" 테이블 행이 하드코딩.
  `DashboardService.get_recent_activities()` 필요.
- `pages/dashboard_page.py:63` — "최근 에러" 행이 하드코딩.
  `DashboardService.get_recent_errors()` 필요.
- 자동 새로고침 없음. 서비스 연결 후에는 ~30초마다(QTimer) 폴링해야 함.
- "전체 프로세스 실행" 버튼이 람다로 인라인 연결되어 있고, 유스케이스 호출이 없음.

**리팩터 계획**
1. `DashboardService`를 `DashboardPage.__init__`에 주입.
2. 서비스를 호출하고 테이블을 다시 채우는 `refresh()` 메서드 추가.
3. `refresh()`에서 `QTimer(interval=30_000)` 시작.
4. "전체 프로세스 실행" → `RunAllUseCase.execute()` → `ScraperWorker.signals.progress_updated`로
   구동되는 `RunAllOverlay`를 표시.

---

## 페이지 2: 데이터 가져오기

**현재 상태**
지사 / 도메인 / 워커 매핑을 보여 주는 정적 테이블. "지사 도메인 가져오기"
버튼은 아무 동작도 하지 않음.

**핵심 이슈**
- `pages/data_import_page.py:24` — 버튼 클릭이 어디에도 연결되어 있지 않음.
  조회는 QThread에서 실행해야 함(PostgreSQL 쿼리).
- `pages/data_import_page.py:31` — "인증 대상" 컬럼이 원시 이메일 주소를 노출.
  표시 전에 마스킹 필요(local part 마지막 4자만, 또는 `***@domain`).
- 가짜 지사 ID로 정적 테이블 행이 하드코딩되어 있음.
- DB 조회 실패 시 에러 상태가 표시되지 않음.

**리팩터 계획**
1. `DataImportService.fetch_branches_from_db()`를 호출하는
   `DataImportWorker(QRunnable)` 작성.
2. 성공 시 `branches_loaded(list[BranchAccountDTO])` 시그널 emit.
3. `DataImportPage` 슬롯이 DTO 리스트로 테이블을 채움.
4. 조회 중 로딩 스피너(또는 버튼 비활성화) 표시.
5. 실패 시 에러 카드 표시.

---

## 페이지 3: 엑셀 다운로드

**현재 상태**
실행 조건 카드가 Windows 경로와 날짜를 하드코딩. 작업 큐 테이블은 정적 행.
"실행" / "선택 상태 강제 완료" 버튼이 모두 미연결.

**핵심 이슈**
- `pages/excel_download_page.py:47` — `QDateEdit` 기본 날짜가 2026-05-12로
  하드코딩. `datetime.date.today() - timedelta(days=1)`가 기본값이어야 함.
- `pages/excel_download_page.py:55` — `QLineEdit` 기본 경로가
  `D:\local_runs\excels` — Windows 전용. `Path(settings.excel_download_dir)`과
  `os.fspath()`로 표시할 것.
- `pages/excel_download_page.py:65` — 스크립트 배지 목록이 하드코딩.
  `ScraperRegistry`(설정 구동)에서 로드.
- `pages/excel_download_page.py:78` — 작업 큐 행이 정적.
  `DownloadService.list_jobs_for_date()`에 연결하고 `ScraperWorker` 시그널로 새로고침.
- `pages/excel_download_page.py:105` — 워커 하트비트 행이 정적.
  `WorkerHeartbeatService.get_live_status()`에 5초 QTimer로 연결.
- "실행" 버튼이 연결되지 않음.
- "선택 상태 강제 완료"가 `ForceCompleteUseCase`에 연결되지 않음.

**리팩터 계획**
1. `"실행".clicked` → `EnqueueDownloadRunUseCase.execute(date, dir, domains)`.
2. 작업당 `ScraperWorker` 하나씩 `QThreadPool.globalInstance()`에 제출.
3. `ScraperWorker.signals.progress_updated` → 슬롯이 해당 테이블 행의
   `progress_cell`을 갱신.
4. `ScraperWorker.signals.job_completed/job_failed` → 슬롯이 상태 배지와
   파일 개수를 갱신.
5. 하트비트 테이블에 5초 `QTimer` 추가.
6. "강제 완료" → `ForceCompleteDialog(selected_job_ids)` → accept 시
   `ForceCompleteUseCase.execute(job_ids, reason)` 호출.

---

## 페이지 4: 정산 실행

**현재 상태**
대상 테이블과 검증 실패 테이블. 둘 다 정적. 버튼들이 다이얼로그는 열지만
유스케이스 호출이 없음. `cellClicked` 꼼수가 7번 컬럼 어디를 클릭하든 다이얼로그를
띄우므로 어떤 버튼을 눌렀는지와 무관하게 발화한다.

**핵심 이슈**
- `pages/settlement_run_page.py:56` — `cellClicked`가 "정산 데이터 매핑"
  버튼이 아니라 7번 컬럼의 어떤 클릭에도 `SettlementMappingDialog`를 띄움.
  실수 클릭에도 발화한다.
- `pages/settlement_run_page.py:65` — 검증 실패 테이블의 금융 컬럼
  (net_amount, lease_fee, withholding_tax)은 금액 연산 영역 —
  **TODO: settlement-logic-specialist에 인계**.
- "전체 정산 실행" 버튼이 연결되지 않음.
- "전체 라이더 매핑"은 다이얼로그를 열지만 DB 쓰기가 수행되지 않음.

**리팩터 계획**
1. `cellClicked` 꼼수를 각 `row_buttons` 위젯의 명명된 슬롯을 통한
   행별 버튼 시그널로 교체.
2. "전체 정산 실행" → `RunSettlementUseCase.execute()` →
   지사별 `SettlementRunWorker(QRunnable)` 디스패치.
3. **금액 연산**(지급액 계산, 검증 비교, 허용 오차 체크)은
   전부 `settlement-logic-specialist`에 위임.
   인터페이스: `calculate_payout(excel_path, branch_code, domain, target_date) -> SettlementResult`.
4. 검증 실패 테이블: 스페셜리스트 함수가 반환하는
   `SettlementResult.failures`로 채운다.

---

## 페이지 5: 모니터링

**현재 상태**
정적 KPI 카드, 워커 상태 테이블, 평문 로그 섹션(행마다 QLabel),
에러 로그 테이블, 에러 상세 패널. 실시간 데이터에 아무것도 연결되어 있지 않음.

**핵심 이슈**
- `pages/monitoring_page.py:44` — 통계 카드의 날짜가 "2026-05-13" 하드코딩.
  `datetime.date.today().isoformat()` 사용.
- `pages/monitoring_page.py:58` — 일반 로그가 행마다 `QLabel` 하나씩 사용.
  확장성이 없다. 일일 로그 파일을 tail하는 `LogTailWorker(QThread)`가 공급하는
  `QPlainTextEdit`(읽기 전용, 고정폭)으로 교체할 것.
  QLabel-per-line 방식은 ~50행이 넘으면 눈에 띄는 UI 지연을 일으킨다.
- `pages/monitoring_page.py:85` — 에러 상세 패널이 정적이며 에러 테이블의
  행 선택에 연결되어 있지 않음.
- `pages/monitoring_page.py:93` — 로그 파일 경로가 하드코딩.
  `settings.log_base_dir / datetime.date.today().isoformat() / worker_id`에서 파생.
- "해당 지사/도메인 재실행" 버튼이 연결되지 않음.
- 워커 상태 / 에러 로그에 자동 새로고침이 없음.

**리팩터 계획**
1. QLabel 로그를 `QPlainTextEdit` + `LogTailWorker(QThread)`로 교체.
   워커는 일일 로그 파일에서 새 라인을 읽어 `new_lines(str)` 시그널을 emit.
2. 에러 테이블 `currentRowChanged` → `MonitoringService.get_error_detail(row_id)`로
   상세 패널 채우기.
3. 워커 상태 테이블에 5초 `QTimer` 추가.
4. 재시도 버튼 → `ExcelDownloadUseCase.retry_job(worker_id, branch, domain)` 연결.

---

## 페이지 6: 결과

**현재 상태**
KPI 카드와 결과 테이블 모두 정적. "전체 전송"이 `SendAllOverlay`를 열지만
정적 62% 바를 보여 줄 뿐 실제 전송 로직은 없음.

**핵심 이슈**
- `pages/results_page.py:38` — "전체 전송"이 오버레이를 동기적으로 열고,
  사용자가 닫으면 오버레이는 사라지지만 실제 전송은 트리거되지 않음.
- `pages/results_page.py:56` — "정산액" 컬럼이 원시 정수 문자열("12,840,500")을
  표시. 포매팅은 공용 금액 포매터 유틸을 써야 함.
  **실제 계산은 settlement-logic-specialist 소관.**
- KPI 카드 하드코딩(정산 완료, 실패 건수, 파일 개수, DynamoDB 카운트).
- 전송 대상 설명이 정적 텍스트 — NAS/S3/DynamoDB 경로는 `StorageSettings`에서
  와야 함.

**리팩터 계획**
1. "전체 전송" → `ResultsService.enqueue_send_all()` → `SendWorker(QRunnable)` 디스패치.
2. `SendWorker`가 `send_progress(step, pct)` emit → `SendAllOverlay` 진행 바.
3. 완료 시 `send_completed(SendResultDTO)` emit → `SendCompleteDialog` 표시.
4. KPI 카드는 `ResultsService.get_summary()`로 채움.
5. 금액 표시: 공용 `presentation/formatters.py` 모듈에
   `format_krw(amount: Decimal) -> str` 구현.

---

## 페이지 7: 설정

**현재 상태**
모든 폼 필드가 Windows 전용 경로와 DB 이름을 포함한 하드코딩 기본 문자열로
채워져 있음. "저장" 버튼이 존재하지 않음.

**핵심 이슈**
- `pages/settings_page.py:44` — `QLineEdit("localhost")`,
  `QLineEdit("delivery_shared")` 등 — `AppSettings`에서 와야 할 값들이 하드코딩.
- `pages/settings_page.py:50` — `QLineEdit(r"D:\keys\settlement-local.key")`는
  Windows 전용 절대 경로. macOS/Linux에서 동작하지 않음.
- `pages/settings_page.py:75` — NAS 경로 `r"D:\local_runs 또는 \NAS\settlement"` —
  Windows 전용. 전부 `pathlib.Path` 사용.
- "저장" 버튼이 없음 — QLineEdit 필드에 입력한 값이 영구 저장되지 않음.
- 스크립트 경로 컬럼이 상대 경로(`scripts/playwright/baemin.py`)를 표시 —
  실제 infrastructure/scrapers 위치로 해석되어야 함.

**리팩터 계획**
1. `AppSettings`를 `SettingsPage.__init__`에 주입.
2. QLineEdit 값을 `settings.*` 필드에서 채움.
3. `SettingsService.save(updated_settings)`를 호출하는 "저장" 버튼 추가.
4. 원시 문자열 경로를 `Path` 렌더링으로 교체: `str(Path(settings.local_excel_dir))`.
5. 스크립트 경로 컬럼: `Path(__file__).parent.parent / "infrastructure" / "scrapers"`로 해석.
6. 워커 목록: `WorkerRegistryService.list_workers()`에서 로드.

---

## 스크래퍼 통합 계획

### 개요

원본 스크립트 두 개
(`coupang_v1_2.py`, `baemin2_commented.py`)는 다음과 같이 이식되었다:

```
infrastructure/scrapers/
  coupang_core.py       — verbatim automation logic, injectable credentials
  coupang_scraper.py    — CoupangScraper (sync, satisfies Scraper protocol)
  baemin_core.py        — verbatim async automation logic, injectable credentials
  baemin_scraper.py     — BaeminScraper (sync adapter around async core)
application/services/
  scraper_protocol.py   — Scraper protocol (Protocol class) + ScraperProgress callback
workers/
  scraper_worker.py     — ScraperWorker(QRunnable) — runs Scraper in thread pool
```

### 인터페이스

```python
# application/services/scraper_protocol.py
class Scraper(Protocol):
    domain: str
    def download_excel(
        self,
        branch_code: str,
        target_date: datetime.date,
        output_dir: str,
        on_progress: ScraperProgress | None = None,
    ) -> list[str]: ...
```

### 데이터 흐름

```
UI "실행" button
  → ExcelDownloadPage._on_run_clicked()
    → EnqueueDownloadRunUseCase.execute(date, output_dir, domains)
      → DownloadJobRepository.create(job)      # persisted before worker starts
      → ScraperWorker(job, scraper, output_dir)
        → QThreadPool.globalInstance().start(worker)
          → worker.run() in thread pool thread
            → scraper.download_excel(branch, date, output_dir, on_progress)
              → (Playwright browser opens, navigates, downloads)
              → returns ["/path/to/file.zip"]
          → signals.job_completed.emit(job_id, file_paths)
            → UI slot: update job row status + file count
            → DownloadJobRepository.mark_completed(job_id, file_paths)
```

### 핵심 결정 사항

1. **원본 그대로 복사, 얇은 어댑터.** Playwright 내부는 재작성하지 않는다.
   `coupang_core.py`와 `baemin_core.py`는 원본 스크립트와 동일하며, 자격 증명
   상수만 함수 파라미터로 치환했다.

2. **동기 프로토콜, 비동기 Baemin은 BaeminScraper가 처리.** QRunnable 워커를
   단순하게 유지하기 위해 `Scraper` 프로토콜은 동기다. `BaeminScraper`는
   호출마다 워커 스레드에서 새 `asyncio` 이벤트 루프를 만든다 —
   워커 스레드에는 Qt 이벤트 루프가 없으므로 안전하다.

3. **자격 증명은 AppSettings / 환경 변수 경유.** `COUPANG_PW`와
   `BAEMIN_PASSWORD`는 소스 코드나 설정 파일이 아니라 환경 변수에서
   스크래퍼 어댑터가 읽는다.

4. **아직 옮기지 않은 헬퍼 파일들.** 두 스크래퍼 모두 원본 프로젝트의
   다음 파일에 의존하며, 아직 복사되지 않았다:
   - `coupang_email_verifier_v1_2.py` → `infrastructure/scrapers/`로 이동 필요
   - `server/` 패키지 (SmsOtpWaiter) → `infrastructure/scrapers/server/`로 이동 필요
   - `baemin_excel_extractor.py` → `infrastructure/scrapers/`로 이동 필요
   이 파일들이 복사되기 전까지는 스크래퍼 임포트 시 `ImportError`가 발생한다.

5. **요기요 자리표시.** 설정 페이지가 `yogiyo.py`에 대해 "추가 예정" 배지를
   보여 준다. 해당 스크래퍼가 작성되면 `Scraper` 프로토콜만 만족하면 되고,
   다른 변경은 필요 없다.

### 구체적인 다음 단계

1. `coupang_email_verifier_v1_2.py`, `server/`, `baemin_excel_extractor.py`를
   `infrastructure/scrapers/`로 복사.
2. `infrastructure/repositories/`에 `DownloadJobRepository` 구현 — 기본 타깃은
   **PostgreSQL** (작업 큐/실행 이력은 관계형 데이터, 기존 `get_pool()` 위에 올린다).
   v5 스키마에는 해당 테이블이 없으므로 운영 도메인과 분리된 `run_state` /
   `download_job` 테이블을 추가하거나 별 스키마(예: `pipeline`)에 둘 것.
   DynamoDB 는 정산 결과 송신용으로 예약되어 있어 본 용도로는 사용하지 않는다 —
   향후 실행 상태 규모가 PostgreSQL 한계를 넘으면 그때 재검토.
3. `EnqueueDownloadRunUseCase.execute()` 구현(현재는 NotImplementedError 발생).
4. `ExcelDownloadPage`의 "실행" 버튼을 유스케이스에 연결.
5. `ScraperWorker.signals.*`를 `ExcelDownloadPage`의 UI 갱신 슬롯에 연결.
6. `tests/integration/` 아래에, 모의 스크래퍼(실제 Playwright 없이)가
   유스케이스 → 워커 → 시그널 경로를 엔드 투 엔드로 도는 통합 테스트 추가.

---

## 금액 연산 책임 경계

다음 항목들은 금융 계산을 포함하거나 참조하며, 본 코드베이스가 아니라
`settlement-logic-specialist`가 소유해야 한다:

| 위치 | 설명 |
|---|---|
| `application/use_cases/run_settlement.py` | 구현 전체 스텁; NotImplementedError 발생 |
| `domain/entities/settlement_run.py:total_payout` | Decimal 필드; 계산은 위임 |
| `presentation/widgets/pages/settlement_run_page.py:65` | 검증 실패 "차이" 컬럼 |
| `presentation/dialogs/settlement_mapping.py:29` | "Net", "기본 지급", "공통 납부", "개별 납부" 컬럼 |
| `presentation/widgets/pages/results_page.py:56` | "정산액" 표시 컬럼 |
| `domain/exceptions.py:SettlementVerificationError` | 예외 타입만; 검증 임계값 로직은 위임 |

인계용 합의 인터페이스:
```python
# to be implemented by settlement-logic-specialist
def calculate_payout(
    excel_path: str,
    branch_code: str,
    domain: str,
    target_date: datetime.date,
) -> SettlementResult:
    """
    Returns SettlementResult with:
      - per_rider: list[RiderPayout]   (Decimal amounts)
      - failures: list[VerificationFailure]
      - total_payout: Decimal
    """
```

---

## 실시간 실행 추적 — 엑셀 다운로드 + 모니터링

### 완료된 작업

`infrastructure/scrapers/`로 복사한 헬퍼 파일:
- `coupang_email_verifier_v1_2.py` — Coupang 로그인용 이메일 OTP 헬퍼
- `baemin_excel_extractor.py` — Baemin 엑셀 다운로드 자동화
- `server/sms_otp_waiter.py` — Baemin 스크래퍼가 쓰는 SMS OTP 수신기

임포트 전략: 헬퍼가 동일 패키지 디렉터리에 있으므로 `coupang_core.py`와
`baemin_core.py` 모두 상대 임포트(`from .helper import ...`)를 사용한다.
core 파일은 두 개의 `try/except ImportError` 블록만 손대는 최소 변경으로 끝났고,
Playwright 자동화 로직 내부는 전혀 수정하지 않았다.

### RunRegistry 설계

`application/services/run_registry.py` — 다음을 수행하는 `QObject` 서브클래스:

- `dict[str, RunState]`를 소유(메모리 보관, 세션당 실행 하나에 항목 하나).
- `register_run(source)`로 새 실행을 등록하고 `RunState`를 반환.
- 워커 스레드에서 Qt 큐드 커넥션으로 호출되는 슬롯 메서드 노출:
  `on_worker_started`, `on_worker_progress`, `on_worker_log`,
  `on_worker_completed`, `on_worker_failed`.
- 양쪽 UI 페이지가 연결하는 상위 시그널을 재전파.

`application/dto/run_state.py` — `RunStatus` 열거형, 타임스탬프, 출력 경로,
에러 메시지, `deque(maxlen=200)` 로그 링 버퍼를 가진 평범한 `@dataclass`.
Qt 의존성이 없어 스레드 간 전달이 안전하다.

### 시그널 계약

| Signal | Args | 의미 |
|---|---|---|
| `run_added` | `run_id: str` | 새 실행 등록(QUEUED) |
| `run_status_changed` | `run_id: str, status: str` | RUNNING / SUCCEEDED / FAILED로 전이 |
| `run_log_appended` | `run_id: str, line: str` | 새 로그 라인 캡처 |
| `run_progress_updated` | `run_id: str, step: str, pct: int` | 스크래퍼의 진행 틱 |

### 스레딩 모델

```
MainWindow (main thread)
  ├─ RunRegistry (QObject, lives on main thread)
  └─ ExcelDownloadPage._on_run_source()
       ├─ registry.register_run()          # on main thread, safe
       └─ make_worker(...)                 # wires signals before submit
            ├─ signals = RunWorkerSignals()  # QObject created on main thread
            └─ QThreadPool.globalInstance().start(worker)
                 └─ worker.run()           # executes on pool thread
                      └─ signals.*.emit()
                           └─ Qt QueuedConnection → registry.on_worker_* (main thread)
                                └─ registry re-emits → ExcelDownloadPage + MonitoringPage
```

`RunWorkerSignals`는 제출 전에 메인 스레드에서 생성된다. Qt가 수신자 스레드
어피니티를 감지해 자동으로 `Qt.QueuedConnection`을 사용한다 — 수동
`invokeMethod`가 필요 없다.

### 아직 남은 TODO

1. **영속화 훅** — `RunRegistry` 는 메모리 보관 상태다. 재시작 후에도 실행 이력이
   살아남도록 기동 시점에 `Callable[[RunState], None]` 영속화 훅을 주입한다.
   기본 타깃은 **PostgreSQL** — `infrastructure/db/postgres.py::get_pool()`
   에 올라타고, v5 스키마와 분리된 `run_state` (또는 별 `pipeline` 스키마) 테이블에
   write. DynamoDB 는 v5 스키마 외부의 정산 송신 다운스트림 원장으로만 도입 예정이며,
   실행 상태 저장소로 쓰지 않는다 — 향후 부하가 커지면 그때 재검토.

2. **동적 워커 개수** — 페이지가 정확히 두 카드(Coupang / Baemin)로
   하드코딩되어 있다. 설정 페이지의 워커 테이블에 연결할 것.

3. **더 깊은 로그 캡처** — core 내부의 `print()`가 캡처되지 않는다.
   `ScraperWorker.run()`에서 실행 시간 동안 `builtins.print`를 몽키패치해
   해당 라인들을 `log_line` 시그널로 emit — core 변경은 없다.

4. **설정 페이지의 자격 증명 저장** — `keyring`에 연결해 사용자가 UI에서
   `COUPANG_PW` / `BAEMIN_PASSWORD`를 설정할 수 있게 한다.

5. **branch_code가 `"local"`로 하드코딩** — 단일 사용자 데스크톱 전용.
   멀티 지사 지원이 추가되면 지사 선택기를 추가한다.

6. **페이지 간 `filter_to_run`** — `ExcelDownloadPage`에
   `monitoring_page_requested(run_id)` 시그널을 추가하고, `MainWindow`에서
   `MonitoringPage.filter_to_run(run_id)`에 연결한다.

7. **RunRegistry 항목 상한** — 상한(예: 최근 50개)을 두거나, N시간 이상 된
   SUCCEEDED/FAILED 실행을 주기적으로 만료시킨다.

---

## 설정 파일 — `~/.settlement_app/config.json`

### 위치

`~/.settlement_app/config.json` (기본값; `SETTLEMENT_APP_CONFIG` 환경 변수로 재정의).

### 형식

```json
{
  "db": {
    "host": "localhost",
    "port": 5432,
    "database": "delivery_shared",
    "aes_key_path": ""
  },
  "storage": {
    "local_excel_dir": "/Users/axxykim/.settlement_app/excels",
    "nas_base_dir": "",
    "s3_bucket": "delivery-settlement",
    "dynamodb_table": "settlement_ledger"
  },
  "scrapers": {
    "coupang_id": "ridestar211p",
    "baemin_id": "ridestar1",
    "sms_server_host": "127.0.0.1",
    "sms_server_port": 8787
  },
  "log_base_dir": "/Users/axxykim/.settlement_app/logs"
}
```

### 보안 규칙

**비밀번호와 AES 키는 절대 이 파일에 저장하지 않는다.** 앱을 실행하기 전에
환경 변수로 설정한다:

```
export COUPANG_PW="..."
export BAEMIN_PASSWORD="..."
```

### 역직렬화 동작

- 누락된 키는 데이터클래스 기본값으로 폴백(향후 버전에서 새 키가 들어와도 관대).
- 알 수 없는 키는 stderr에 `WARNING`을 출력하지만 예외를 발생시키지 않음(이름 변경 후 구설정에 관대).
- `dataclasses.fields()`가 루프를 구동 — 하드코딩된 필드 목록 없음.
