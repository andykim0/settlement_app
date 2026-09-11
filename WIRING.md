# WIRING.md — 버튼 & 라벨 로드맵

## 범례
- ✅ 연결 완료 (실제 동작이 이미 구현됨)
- 🟡 부분 연결 (플레이스홀더 동작, 실제 서비스 연결 필요)
- ⚫ 스텁 (아무 동작 없거나 단순히 `self.accept()` / `self.reject()` 호출)
- 📊 목업 데이터 (라벨이 하드코딩된 값만 표시, 실시간 바인딩 아님)

## 표기 규칙

**"Target action"** 컬럼은 사용자 관점에서 버튼/라벨이 _수행해야 하는_ 동작을 한 문장으로 기술한다.
**"Where to wire"** 컬럼은 해당 로직을 담아야 할 레이어를 명시한다: route handler → service → repository, 이 데스크톱 앱에서는 widget slot → service/use-case → repository. `(NEW)` 표기된 파일은 아직 존재하지 않으며, 명시된 메서드명은 제안 인터페이스다. 금액 계산 항목은 `→ settlement-logic-specialist owns the math`로 표시했으며, 이는 정산금 계산, 수수료 차감, 반올림, 검증 델타 로직을 이 에이전트에서 구현하면 안 되기 때문이다.

---

## Dashboard (`src/settlement_app/presentation/widgets/pages/dashboard_page.py`)

### 이미 연결됨
- `전체 프로세스 실행` 버튼: `RunAllConfirmDialog`를 연다 (line 24). 다이얼로그 자체는 스텁 — Dialogs 섹션 참고.

### 버튼
| Element | Current | Target action | Where to wire |
|---|---|---|---|
| `전체 프로세스 실행` (header, line 23) | 🟡 다이얼로그는 열리지만 동작 없음 | 확인 후 전체 파이프라인을 한 번에 큐잉 | `RunAllConfirmDialog` → `application/use_cases/run_all_pipeline.py` (NEW) `RunAllPipelineUseCase.execute()` |

### 동적 라벨
| Element | Current | Should bind to | Source |
|---|---|---|---|
| `오늘 대상 지사` StatCard 값 `"16개"` (line 35) | 📊 | DB에서 가져온 실시간 지사 수 | `DashboardService.get_stats()` → `DashboardStatsDTO.branch_count` |
| `오늘 대상 지사` footer `"PostgreSQL 동기화 완료"` (line 36) | 📊 | 마지막 동기화 시각 또는 동기화 상태 | `DashboardService.get_stats()` — `DashboardStatsDTO`에 `last_sync_at: datetime \| None` 추가 |
| `Excel Download` StatCard 값 `"12 / 16"` (line 38) | 📊 | 오늘 다운로드 작업의 실시간 완료/전체 | `DashboardStatsDTO.excel_done` / `.excel_total` |
| `Excel Download` footer `"실행 중 2 · 에러 1"` (line 38) | 📊 | 실시간 실행 중/에러 카운트 | `DashboardStatsDTO.excel_running` / `.excel_error` |
| `정산 검증` StatCard 값 `"9 / 16"` (line 39) | 📊 | 실시간 정산 완료/전체 | `DashboardStatsDTO.settlement_done` / `.settlement_total` |
| `정산 검증` footer `"검증 실패 2건"` (line 39) | 📊 | 실시간 실패 카운트 | `DashboardStatsDTO.settlement_fail` |
| `전송 대기` StatCard 값 `"7건"` (line 40) | 📊 | 전송 대기 중인 결과 수 | `DashboardStatsDTO.send_pending` |
| `최근 작업` 테이블 행 (lines 53–56) | 📊 | 실시간 최근 활동 행 | `DashboardService.get_recent_activities()` — 이미 스텁 존재; 반환값을 테이블 채우기에 연결 |
| `최근 에러` 테이블 행 (lines 64–66) | 📊 | 실시간 최근 에러 행 | `DashboardService.get_recent_errors()` — 이미 스텁 존재; 반환값을 테이블 채우기에 연결 |

---

## Data Import (`src/settlement_app/presentation/widgets/pages/data_import_page.py`)

### 버튼
| Element | Current | Target action | Where to wire |
|---|---|---|---|
| `지사 도메인 가져오기` (header, line 27) | ⚫ 연결 없음 | PostgreSQL에서 branch+domain+worker 매핑을 가져와 테이블 갱신 | `application/services/data_import_service.py` (NEW) `DataImportService.fetch_branches_from_db()` — 슬롯이 아니라 `QRunnable` 워커에서 실행해야 함 |

### 동적 라벨
| Element | Current | Should bind to | Source |
|---|---|---|---|
| `가져온 지사별 도메인 계정` 테이블 행 (lines 37–45) | 📊 | PostgreSQL에서 가져온 실시간 `BranchAccountDTO` 리스트 | `DataImportService.fetch_branches_from_db()` → `list[BranchAccountDTO]`; `인증 대상` 컬럼은 전체 주소를 마스킹하고 마지막 4자만 노출 |

---

## Excel Download (`src/settlement_app/presentation/widgets/pages/excel_download_page.py`)

### 이미 연결됨
- Coupang `실행` 버튼: 환경변수 검증, run 등록, `QThreadPool`로 `ScraperWorker` 디스패치 (line 262–263, `_on_run_source("coupang")`).
- Baemin `실행` 버튼: 동일 경로 (line 265–268, `_on_run_source("baemin")`).
- `전체 실행` 헤더 버튼: `_on_run_all()` 호출 → 양쪽 소스 실행 (line 212–213).
- Coupang `로그 보기` / Baemin `로그 보기`: Monitoring 페이지 인덱스 4로 이동 (line 333–339). `filter_to_run()` 호출은 아직 TODO.
- 두 워커 카드의 상태 라벨 (`_status_lbl`, `_ts_lbl`, `_step_lbl`, `_output_lbl`, `_error_lbl`): registry 시그널을 통한 `update_run(RunState)`로 완전 구동 (line 139–182).

### 버튼
| Element | Current | Target action | Where to wire |
|---|---|---|---|
| `로그 보기` (coupang card, line 134) | 🟡 Monitoring으로 이동하지만 run 사전 선택 안 됨 | Monitoring 페이지의 run 선택기에 해당 소스의 마지막 run_id를 미리 세팅 | `ExcelDownloadPage._on_view_logs()` line 333: 이동 후 `self._monitoring_page.filter_to_run(run_id)` 호출 — `run_id`는 `self._last_run_id[source]`에서 가져옴 |
| `로그 보기` (baemin card, line 134) | 🟡 위와 동일 | 동일 | 동일 |

### 동적 라벨
| Element | Current | Should bind to | Source |
|---|---|---|---|
| `대상 날짜` `QDateEdit` 기본값 (line 226) | ✅ 어제로 기본 설정됨 | — | `datetime.date.today() - timedelta(days=1)`로 이미 정상 |
| `저장 디렉토리` `QLineEdit` 기본값 (line 237) | ✅ `AppSettings.storage.local_excel_dir`에서 읽음 | — | 이미 정상 |
| `도메인` 뱃지 (lines 244–245) | 📊 하드코딩된 `baemin` + `coupang` | `AppSettings`에 설정되었거나 `DataImportService`에서 발견된 도메인을 반영 | `application/services/data_import_service.py` (NEW) `.list_active_domains()` |

---

## Settlement Run (`src/settlement_app/presentation/widgets/pages/settlement_run_page.py`)

### 버튼
| Element | Current | Target action | Where to wire |
|---|---|---|---|
| `전체 정산 실행` (header, line 26) | ⚫ 연결 없음 | 대기 중인 전체 대상의 정산 작업을 큐잉하고 즉시 반환 | `application/use_cases/run_settlement.py` `RunSettlementUseCase` — 스텁 존재; **→ settlement-logic-specialist owns the math; 이 버튼은 use case 큐잉만 담당** |
| `전체 라이더 매핑` (header, line 27) | 🟡 정적 데이터로 `RiderMappingDialog`를 연다 | 모든 대기 지사의 실제 Excel vs DB diff로 채워진 다이얼로그를 연다 | `RiderMappingDialog` 생성자에 `branch_id` + `excel_path` 전달; `application/services/rider_mapping_service.py` (NEW) `RiderMappingService.compare_excel_to_db(branch_id, excel_path)` 호출 |
| 행별 `정산` 버튼 (column 7, line 47) | ⚫ 실제 연결 없음 | 해당 행의 branch+domain에 대한 정산 작업 큐잉 | 동일하게 `RunSettlementUseCase.execute(branch_code, domain, ...)` — **→ settlement-logic-specialist** |
| 행별 `라이더 매핑` 버튼 (column 7, lines 47, 59) | 🟡 정적 데이터로 `RiderMappingDialog`를 연다 | 해당 행의 지사 범위로 다이얼로그를 연다 | `RiderMappingDialog`에 `(branch_code, excel_path)` 전달; 위와 동일 서비스 |
| 행별 `정산 데이터 매핑` 버튼 (column 7, lines 47, 50, 55) | 🟡 col 7의 모든 클릭이 정적 데이터로 `SettlementMappingDialog`를 연다 | 해당 지사 run의 실제 매핑 행으로 채워진 다이얼로그를 연다 | `SettlementMappingDialog`에 `(branch_id, run_id)` 전달; `application/services/settlement_verification_service.py` (NEW) `SettlementVerificationService.get_mapping_rows(branch_id, run_id)` 호출 |
| 행별 `재정산` 버튼 (guro_03 row, line 51) | ⚫ 연결 없음 | 이전에 실패한 행에 대한 정산 작업 재큐잉 | `RunSettlementUseCase.execute(branch_code, domain, ...)` — **→ settlement-logic-specialist** |

### 동적 라벨
| Element | Current | Should bind to | Source |
|---|---|---|---|
| `정산 대상` 테이블 행 (lines 43–59) | 📊 | 실시간 `SettlementTargetRow` 리스트 | `application/services/settlement_run_service.py` (NEW) `SettlementRunService.list_targets_for_today()` → `list[SettlementTargetRow]` |
| `검증 실패` 테이블 행 (lines 76–78) | 📊 | 실시간 `ValidationFailureRow` 리스트 | `SettlementRunService.get_validation_failures()` — **델타 값은 금액; → settlement-logic-specialist** |

---

## Monitoring (`src/settlement_app/presentation/widgets/pages/monitoring_page.py`)

### 이미 연결됨
- `← 뒤로` 페이지 내 버튼: `back_requested` 시그널 emit → `MainWindow._on_back()` (line 175–178). `set_back_enabled()`로 활성/비활성.
- Run 선택기 `QComboBox`: 인덱스 변경 시 로그 뷰 필터링 (line 209, `_on_selector_changed`).
- `지우기` 버튼: `_log_view` 클리어 (line 213–214).
- `실행 목록` 행: `RunRegistry` 시그널로 자동 채워지고 갱신됨 (lines 269–293).
- 로그 영역 `_log_view`: `registry.run_log_appended` 시그널의 실시간 로그를 추가 (line 295–299).

### 버튼 / 인터랙티브 위젯
| Element | Current | Target action | Where to wire |
|---|---|---|---|
| `WorkerErrorDetailPanel` — `해당 지사/도메인 재실행` (worker_error_detail.py:58) | ⚫ 연결 없음 | 선택된 worker+branch+domain의 실패 작업 재시도 | `application/use_cases/retry_download_job.py` (NEW) `RetryDownloadJobUseCase.execute(worker_id, branch_code, domain)` |
| `WorkerErrorDetailPanel` — `로그 파일 열기` (worker_error_detail.py:61) | ⚫ 연결 없음 | OS 기본 뷰어로 에러 로그 파일 열기 | `application/services/filesystem_service.py` (NEW) `FilesystemService.open_file(path: str)` — `QDesktopServices.openUrl` 사용; 이벤트 루프 블로킹 금지 |
| `WorkerErrorDetailPanel` 패널 자체 | 📊 WORKER-02 / guro_03 값이 하드코딩됨 | run 행 선택 시 채워져야 함 | `MonitoringPage`에 행 클릭 시그널 → `WorkerErrorDetailDTO` 필요; 패널이 현재 `MonitoringPage` 레이아웃에 노출되지 않으므로 먼저 도킹 필요 |

### 동적 라벨
| Element | Current | Should bind to | Source |
|---|---|---|---|
| `WorkerErrorDetailPanel` 테이블 행 (worker_error_detail.py:49–53) | 📊 | 선택된 run의 에러 필드 | 행 선택 시 `MonitoringPage`에서 `WorkerErrorDetailDTO` 전달 |
| `WorkerErrorDetailPanel` 로그 파일 경로 (worker_error_detail.py:52) | 📊 하드코딩 경로 | `settings.log_base_dir / date / worker_id / …` | `AppSettings.log_base_dir` + `RunState.run_id` |

---

## Results (`src/settlement_app/presentation/widgets/pages/results_page.py`)

### 버튼
| Element | Current | Target action | Where to wire |
|---|---|---|---|
| `전체 전송` (header, line 26) | 🟡 62%가 하드코딩된 `SendAllOverlay`를 연다 | 백그라운드 send-all 작업을 큐잉; 진행률 바가 실제 진행 상황 반영 | `application/use_cases/send_all_results.py` (NEW) `SendAllResultsUseCase.execute()` → `SendAllOverlay`로 progress 시그널 emit |
| 행별 `상세` 버튼 (yeouido_01, mapo_02, seocho_05 rows, lines 60, 64, 72) | ⚫ 연결 없음 | 지사 결과 상세 뷰 열기 (새 다이얼로그 또는 사이드 패널) | `application/services/results_service.py` (NEW) `ResultsService.get_branch_detail(branch_code, run_id)` → `BranchResultDetailDTO` |
| 행별 `전송` 버튼 (yeouido_01 row, line 60) | ⚫ 연결 없음 | 해당 지사의 결과를 DynamoDB + S3 + NAS로 전송 | `SendAllResultsUseCase.execute(branch_codes=[branch_code])` 또는 `ResultsService.send_branch(branch_code)` |
| 행별 `실패 보기` 버튼 (guro_03 row, line 68) | ⚫ 연결 없음 | 해당 지사의 검증 실패 행 표시 | `SettlementVerificationService.get_mapping_rows(branch_id, run_id)` (SettlementRunPage와 동일 서비스) |

### 동적 라벨
| Element | Current | Should bind to | Source |
|---|---|---|---|
| `정산 완료` StatCard `"14 / 16"` (line 38) | 📊 | 실시간 완료/전체 카운트 | `application/services/results_service.py` (NEW) `ResultsService.get_summary()` → `ResultsSummaryDTO.settlement_done/.settlement_total` |
| `정산 완료` footer `"전송 가능 12건"` (line 39) | 📊 | 전송 가능 수 | `ResultsSummaryDTO.sendable_count` |
| `검증 실패` StatCard `"2건"` (line 40) | 📊 | 실시간 실패 카운트 | `ResultsSummaryDTO.verification_fail_count` |
| `S3/NAS 파일` StatCard `"28개"` (line 42) | 📊 | 실시간 파일 카운트 | `ResultsSummaryDTO.s3_nas_file_count` |
| `DynamoDB DAILY` StatCard `"1,284건"` (line 43) | 📊 | 실시간 DynamoDB 아이템 수 | `ResultsSummaryDTO.dynamodb_daily_count` |
| `지사별 결과 리스트` 테이블 행 (lines 57–72) | 📊 | 실시간 `ResultBranchRow` 리스트 | `ResultsService.list_branch_results()` → `list[ResultBranchRow]` |

---

## Settings (`src/settlement_app/presentation/widgets/pages/settings_page.py`)

### 버튼
| Element | Current | Target action | Where to wire |
|---|---|---|---|
| _(아직 명시적 저장/테스트 버튼 없음)_ | — | 카드 섹션마다 `저장` 버튼 추가 (PostgreSQL, Storage) | `application/services/settings_service.py` (NEW) `SettingsService.save_db_config()`, `SettingsService.save_storage_config()` |

### 동적 라벨 / 입력
| Element | Current | Should bind to | Source |
|---|---|---|---|
| PostgreSQL `Host` `QLineEdit` (line 44) | 📊 `"localhost"` | 페이지 오픈 시 `AppSettings.db.host`에서 로드 | `infrastructure/settings/app_settings.py` `AppSettings` |
| PostgreSQL `Database` `QLineEdit` (line 45) | 📊 `"delivery_shared"` | `AppSettings.db.database` | 동일 |
| PostgreSQL `AES 키 위치` `QLineEdit` (line 48) | 📊 v5 와 불일치 — 단일 키 경로 컨셉 폐기 | v5 는 컬럼별 `encryption_key_alias` 로 ENV/AWS KMS 의 raw key 를 lookup. UI 는 alias→ENV 매핑 표시 또는 alias 목록 표시로 재설계(또는 제거) | `infrastructure/settings/app_settings.py` + 신규 `EncryptionKeyResolver` 인터페이스 |
| `저장/전송 설정` — `로컬/NAS 경로` (line 72) | 📊 하드코딩 | `AppSettings.storage.local_excel_dir` | 동일 |
| `저장/전송 설정` — `S3 Bucket` (line 74) | 📊 `"delivery-settlement"` | `AppSettings.storage.s3_bucket` | 동일 |
| `저장/전송 설정` — `DynamoDB Table` (line 76) | 📊 `"settlement_ledger"` | `AppSettings.storage.dynamodb_table` | 동일 |
| `도메인별 스크립트` 테이블 행 (lines 59–61) | 📊 | settings 또는 `ScraperRegistry`의 스크립트 레지스트리 | `application/services/settings_service.py` (NEW) `SettingsService.list_domain_scripts()` |
| `Worker 장비 목록` 테이블 행 (lines 87–89) | 📊 | 실시간 worker 리스트 + heartbeat 상태 | `application/services/worker_registry_service.py` (NEW) `WorkerRegistryService.list_workers()` → `list[WorkerRow]` |
| `실행 기본값` 테이블 행 (lines 101–105) | 📊 | `AppSettings` 기본값 | `SettingsService.get_run_defaults()` → 페이지 오픈 시 바인딩; 저장 시 영속화 |

---

## Dialogs

### RunAllConfirmDialog (`src/settlement_app/presentation/dialogs/run_all_confirm.py`)

| Element | Current | Target action | Where to wire |
|---|---|---|---|
| `실행 시작` 버튼 (line 45) | ⚫ `self.accept()`만 호출 | 전체 파이프라인 큐잉 트리거 후 다이얼로그 종료 | 호출 측(`DashboardPage`)이 `dialog.accepted`에 연결; `application/use_cases/run_all_pipeline.py` (NEW) `RunAllPipelineUseCase.execute()` 호출 |
| `취소` 버튼 (line 44) | ✅ `self.reject()` 호출 | — | 이미 정상 |
| 단계 리스트 라벨 (lines 30–37) | 📊 6단계 하드코딩 | 실제 실행 단계 반영 | `RunAllPipelineUseCase.describe_steps()` — 다이얼로그 `__init__`에서 채움 |

### RiderMappingDialog (`src/settlement_app/presentation/dialogs/rider_mapping.py`)

| Element | Current | Target action | Where to wire |
|---|---|---|---|
| 테이블 행 (lines 27–29) | 📊 정적 | 선택 지사의 실제 Excel vs DB 비교 | `application/services/rider_mapping_service.py` (NEW) `RiderMappingService.compare_excel_to_db(branch_id, excel_path)` — 다이얼로그는 `(branch_id, excel_path)`를 생성자 파라미터로 받아야 함 |
| `PostgreSQL 업데이트` 버튼 (line 33) | ⚫ `self.accept()`만 호출 | 미등록 라이더를 PostgreSQL에 영속화 후 종료 | `RiderMappingService.apply_updates(branch_id, mapping_result)` — `self.accept()` 이전에 호출 |

### SettlementMappingDialog (`src/settlement_app/presentation/dialogs/settlement_mapping.py`)

| Element | Current | Target action | Where to wire |
|---|---|---|---|
| 테이블 행 (lines 29–31) | 📊 정적 금액 값 | 선택 지사 run의 라이더별 실제 매핑 행 | `application/services/settlement_verification_service.py` (NEW) `SettlementVerificationService.get_mapping_rows(branch_id, run_id)` — **금액 컬럼 (기본 지급, 공통 납부, 개별 납부, Net) → settlement-logic-specialist** |
| `닫기` 버튼 (line 39) | ✅ `self.accept()` 호출 | — | 이미 정상 |

### ForceCompleteDialog (`src/settlement_app/presentation/dialogs/force_complete.py`)

| Element | Current | Target action | Where to wire |
|---|---|---|---|
| 테이블 행 (lines 26–27) | 📊 정적 | 선택 ID로 필터링된 강제 처리 가능 작업의 실제 리스트 | `application/use_cases/force_complete.py` (NEW) `ForceCompleteUseCase.get_forceable_jobs(job_ids)` |
| `완료 처리` 버튼 (line 41) | ⚫ `self.accept()`만 호출 | 선택 작업을 사유 텍스트와 함께 강제 완료 처리 | `ForceCompleteUseCase.execute(job_ids, reason=self.reason.toPlainText())` — `self.accept()` 이전에 호출 |
| `취소` 버튼 (line 40) | ✅ `self.reject()` 호출 | — | 이미 정상 |

### SendCompleteDialog (`src/settlement_app/presentation/dialogs/send_complete.py`)

| Element | Current | Target action | Where to wire |
|---|---|---|---|
| 뱃지 라벨 `"DynamoDB 1,284 items"`, `"S3 28 files"`, `"NAS 28 files"` (lines 28–30) | 📊 하드코딩 | 완료된 send 작업이 반환한 카운트 | `SendAllResultsUseCase.execute()`가 반환하는 `SendResultDTO`; 다이얼로그 생성자에 전달 |
| `확인` 버튼 (line 35) | ✅ `self.accept()` 호출 | — | 이미 정상 |

### SendAllOverlay / RunAllOverlay (`src/settlement_app/presentation/dialogs/send_complete.py`)

| Element | Current | Target action | Where to wire |
|---|---|---|---|
| 62%인 `QProgressBar` (line 58) | 📊 하드코딩 | 실제 작업 진행률 반영 | 백그라운드 작업이 `progress_updated(int)` 시그널 emit; 다이얼로그 슬롯에서 `bar.setValue(pct)` 호출 |
| `현재 단계` 라벨 (line 69) | 📊 단계 텍스트 하드코딩 | 실제 현재 단계 설명 반영 | 작업이 `step_changed(str)` 시그널 emit → `step.setText(text)` |

---

## 횡단 관심사 (MainWindow + 공용 위젯)

### MainWindow (`src/settlement_app/presentation/main_window.py`)

| Element | Current | Target action | Where to wire |
|---|---|---|---|
| 헤더 `←` 뒤로 버튼 (line 47–53) | ✅ `_history` 스택을 통한 뒤로 가기 동작 | — | 이미 정상 |
| `_SideNav` 버튼 (lines 83–89) | ✅ `QStackedWidget` 인덱스 전환 | — | 이미 정상 |
| `ExcelDownloadPage._on_view_logs` run_id 전달 (line 340) | 🟡 Monitoring으로 이동하지만 `filter_to_run` 미호출 | 이동 후 `self._monitoring_page.filter_to_run(run_id)` 호출 필요 | `main_window.py` line 339–340: `window.stack.setCurrentIndex(4)` 이후 `window._monitoring_page.filter_to_run(run_id)` 추가 |

### StatCard (`src/settlement_app/presentation/widgets/cards.py:12`)

| Element | Current | Target action | Where to wire |
|---|---|---|---|
| `StatCard.val` 및 `StatCard.foot` 라벨 (line 32, 39) | 📊 생성 시에만 설정 | 실시간 presenter 푸시를 위한 `update_value(value, foot)` 슬롯 노출 | cards.py line 51 TODO에 명시된 메서드 추가: `def update_value(self, value: str, foot: str = "") -> None` |

---

## 우선순위 로드맵

다음 10개 항목은 가치/노력 비율 기준으로 정렬 — 레버리지가 가장 높은 항목이 최상위.

---

**1. Dashboard 실시간 데이터 바인딩** (S)
`DashboardPage`의 stat 카드와 두 테이블을 이미 스텁된 `DashboardService` 메서드에 연결.
`StatCard`에 `update_value()` 추가와 `_populate_table()` 헬퍼 필요. 새 서비스 불필요 —
스텁이 이미 존재하고 타입드 DTO를 반환.
파일: `dashboard_page.py`, `cards.py:51`, `application/services/dashboard_service.py`
노력: S

---

**2. Excel Download — "로그 보기" 시 Monitoring에 `run_id` 전달** (S)
한 줄 수정: `window.stack.setCurrentIndex(4)` 이후 `window._monitoring_page.filter_to_run(self._last_run_id[source])` 호출.
이미 연결된 다운로드 플로우의 유일한 실제 UX 갭 제거.
파일: `excel_download_page.py:340`, `main_window.py`
노력: S

---

**3. Settings 페이지 — AppSettings에서 로드** (S)
`SettingsPage.__init__`에서 `AppSettings`를 읽어 모든 `QLineEdit` 필드를 미리 채움.
섹션마다 `저장` 버튼을 추가하고 새 `SettingsService.save_config()`에 연결.
하드코딩된 Windows 경로(line 48, 72)는 macOS에서 정확성 버그 — 이를 수정.
파일: `settings_page.py`, `application/services/settings_service.py` (NEW)
노력: S

---

**4. Data Import — "지사 도메인 가져오기" 버튼 연결** (M)
`DataImportService.fetch_branches_from_db()` (PostgreSQL 쿼리)를 구현하고 `QRunnable`에서 실행,
지사 테이블 채우기. 실제 지사 데이터가 필요한 모든 하위 페이지의 의존성을 해소.
파일: `data_import_page.py:27`, `application/services/data_import_service.py` (NEW)
노력: M — PostgreSQL 연결이 살아있어야 함

---

**5. Results 페이지 — 실시간 KPI 카드 + 테이블** (M)
`ResultsService.get_summary()` 및 `ResultsService.list_branch_results()` 스텁 → 실제 DB 쿼리 추가.
4개 `StatCard` 값과 지사별 결과 테이블 연결.
DTO (`ResultsSummaryDTO`, `ResultBranchRow`)는 이미 `settlement_dto.py`에 존재.
파일: `results_page.py`, `application/services/results_service.py` (NEW)
노력: M

---

**6. RiderMappingDialog — 실제 비교 + 적용** (M)
다이얼로그는 `(branch_id, excel_path)`를 생성자 파라미터로 받아야 함.
`RiderMappingService.compare_excel_to_db()`로 Excel 행을 PostgreSQL 라이더 테이블과 diff,
`apply_updates()`로 신규 라이더 영속화. `PostgreSQL 업데이트` 버튼 연결.
파일: `rider_mapping.py`, `settlement_run_page.py:28,59`, `application/services/rider_mapping_service.py` (NEW)
노력: M — Data Import (#4) 선행 필요

---

**7. ForceCompleteDialog — 실제 작업 리스트 + 실행** (M)
`ForceCompleteUseCase.get_forceable_jobs(job_ids)`를 `DownloadJobRepository` 기반으로 구현,
`execute(job_ids, reason)`로 상태 설정 + 감사 로그 기록.
`완료 처리` 버튼이 `self.accept()` 이전에 use case를 호출하도록 연결.
파일: `force_complete.py:41`, `application/use_cases/force_complete.py` (NEW)
노력: M

---

**8. WorkerErrorDetailPanel — MonitoringPage에 도킹 + 버튼 연결** (L)
패널은 다이얼로그 파일에 존재하지만 `MonitoringPage`에 표시되지 않음.
`_RunRow`에 클릭 시그널 추가 → `RunState`에서 `WorkerErrorDetailPanel` 채우기.
`로그 파일 열기`를 `FilesystemService.open_file()`에, `재실행`을 `RetryDownloadJobUseCase`에 연결.
파일: `worker_error_detail.py`, `monitoring_page.py`, `application/services/filesystem_service.py` (NEW), `application/use_cases/retry_download_job.py` (NEW)
노력: L

---

**9. SendAllOverlay — 실제 진행률 시그널** (L)
`SendAllResultsUseCase` (NEW)는 Qt 시그널로 진행률을 emit해야 오버레이의 바와 단계 라벨이
실시간 유지됨. `RunRegistry`가 이미 확립한 패턴 — send 작업에도 동일하게 적용.
파일: `send_complete.py:58,69`, `results_page.py:27`, `application/use_cases/send_all_results.py` (NEW)
노력: L — Results 서비스(#5)와 합의된 DynamoDB/S3/NAS 클라이언트 인터페이스에 의존

---

**10. Settlement Run — 큐잉 + 검증 표시** (XL)
`전체 정산 실행`, 행별 `정산`, `재정산` 버튼 모두 `RunSettlementUseCase`로 연결.
use case 스텁이 스페셜리스트용 인터페이스를 이미 문서화하고 있음.
**→ settlement-logic-specialist owns all money math** (정산금 계산, 수수료/공제, 세금, 반올림,
Python vs Excel 검증). 이 에이전트의 범위는: 버튼 → 작업 큐잉 → DB의 작업 행 → 상태 폴링.
파일: `settlement_run_page.py:26,47,51,59`, `application/use_cases/run_settlement.py`, `application/services/settlement_run_service.py` (NEW)
노력: XL — settlement-logic-specialist의 `calculate_payout()` 인터페이스 전달 대기 중
