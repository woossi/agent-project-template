# 작업

## 상태
진행 중 (생활인구·동코드매핑·전월세실거래·duckdb환경 완료, 합의 4건 dc확정 / 생활이동=사용자 수집승인 대기 / 당근=danggeun-scraper 스키마계약 대기)

## 목표
UMC 원천 데이터(생활인구·실거래 CSV)를 압축 포맷으로 전환·스키마화하고 쿼리 가능한 압축 DB 인프라 계층 구축.

## 현재 작업
압축 DB 인프라 — 생활인구 전체 변환·검증 완료, 공유위치 `project/umc/data/compressed_db/`로 이동, 동코드매핑 차원테이블 완료. 다음 우선순위(전월세실거래) 대기.

### 완료
- 원천 인벤토리 실측 + 스키마 파악, PoC 변환·검증(202405).
- 포맷 결정: Parquet+ZSTD-9, 파티션키 year_month. 1차 문서 `01_format_decision_and_plan.md`.
- **dedup 규칙 확정**: 02. vs 03.은 동일원천의 정밀도/포맷 변형(03.=02. 소수1자리 반올림). 유효 39개월(202301~202603), 03.에서 16 + 02.에서 23. tmp/202509 md5 동일 무시. → `02_dedup_decision.md`.
- **전체 변환 실행 완료**: 39개월 → `db/living_pop_dong/year_month=<YM>/part-0.parquet` (zstd-9). 4.60GB→1.36GB (3.37x). 12,048,308행.
- **3중 무결성 검증 39/39 PASS**: 행수·total_pop합계·라운드트립·독립CSV 진실값 대조 → `_validation.csv`.
- 전역 dataset open + 샘플쿼리 3종 정상(6/3.6/45ms). `_schema.json`(소비 계약) 생성.
- 인코딩 이슈 해결: 202509 헤더 CP949 손상 → latin-1 디코드로 흡수(데이터행 ASCII, 무영향).
- 202509 결측 76행 좌표 규명(20250918 00시·23시, 원본 누락).
- 인터페이스 규격 문서 `03_living_pop_interface.md` 작성.
- orchestrator 승인 수신(39/39 PASS) + 합의 4건 방향 수신·ack.
- **#1 공유위치 확정·실행**: DB를 `project/umc/data/compressed_db/`로 mv(단일소스, 디스크중복 0), `.gitignore` 등록, _schema.json root_path 갱신, 새 위치 재검증(샘플쿼리 정상). 스크립트 DB_ROOT 갱신.
- **#4 동코드매핑 전환 완료**: dim_adm_dong(424행, 동코드↔동명·자치구 조인키, sigungu_code 파생) + dim_inflow_region(96행, 생활이동 출발지). living_pop 커버리지 100%·동집합 일관성 검증 PASS. 각 _schema.json 동봉.

- **#1·#4 완료 보고 발송**(orchestrator+dc), dc #2·#3 합의 요청 발송. orchestrator 승인 수신·ack.
- **#3 정밀도 단차 경고 명시**: orchestrator 지시대로 living_pop _schema.json known_issues에 severity=warning·affects=[stats-validator,data-curator] 추가, finalize_schema.py 갱신·재생성.
- **전월세실거래 재기록 완료(#6)**: SNAPPY 6chunk·60만행 → ZSTD-9 10파티션(year_month=CTRT_DAY, 202506~202603) 8.67MB. 행수·연월·자치구분포·컬럼 보존, dim_adm_dong 자치구 조인 커버리지 검증 PASS. CGG_CD 빈값 5행 보존. _schema.json·_validation.csv 동봉. 공유DB rental_tx 편입.
- **환경요청 발송**: duckdb + 생활이동 수집주체. orchestrator 회신 수신·ack.
- **합의 4건 dc 확정 수신**: #2 스네이크 수용, #3 단차 현상태+문서명시+소비측규약(분석노트·캡션 명시·구간분리). #1·#4 수용. 당근 3자합의 동의.
- **duckdb 환경 구축(orchestrator pipx승인→실측 venv로 정정)**: pipx는 라이브러리 불가(실증) → 격리 venv `compressed_db/.duckdb-venv`(duckdb 1.5.4, 시스템 인터프리터 무오염, 57MB, git미추적). 팩트×차원 SQL 조인 실동작 검증(rental_tx×dim, living_pop×dim). numpy/pandas 미설치라 .df() 불가·.fetchall() 사용 — README_consume.md에 명시.
- **소비 가이드 작성**: `compressed_db/README_consume.md`(pyarrow 1급·duckdb 2급 경로, 정밀도 단차 규약, rental_tx 주의).

- **생활이동 수집 승인 수신**(orchestrator, 사용자 확정): de가 수집+압축 일괄 담당. 공공데이터라 리스크 낮음.
- **생활이동 규모 실측**: 1일=CSV 155MB·236만행, parquet-zstd9 22.9MB(6.76x). 762일 추정 CSV ~118GB·parquet ~17.5GB. 로컬 디스크 28GB로 동시보관 불가.
- **저장 백엔드 결정(사용자)**: iCloud Drive 적재(로컬 placeholder/캐시, 실저장 클라우드). 로컬 28GB 제약 우회. 적재 위치 `~/Library/Mobile Documents/com~apple~CloudDocs/umc-compressed-db/seoul_migration_od/`.
- **스트리밍 수집 스크립트 작성·실행(진행중)**: collect_migration_streaming.py. 일자별 다운로드→추출→parquet→iCloud 적재→ZIP/CSV 즉시삭제(피크 로컬 ~190MB). 파일럿(20240101) 엔드투엔드 검증 PASS. 백그라운드 실행 중(PID 로그: .context/db-infra/logs/). 진행 20/762일 정상(누적 5948만행, .stream_tmp 0B=즉시삭제 동작).

- **dc `_data_registry.md` 등재 인지**: 4DS 카탈로그+#3 규약(a~d)+캡션 표준문안. 생활이동(5번째 DS)은 미등재(수집 중)→완료 후 dc에 등재정보 제공 필요.
- **당근 전환 대기 확정**: orchestrator 통지 — danggeun-scraper ToS 검토서 자동수집 보류 권고 → 20컬럼 스키마 합의 자체 보류 가능. 당근 적극추적 중단.
- **iCloud 동작 실측·전략 조정**: ① brctl evict는 업로드 완료 후에만 가능(즉시 우회 불가, -2008). ② 업로드가 사실상 정체(2분간 evict +3 후 0, 로컬 점유 수집속도대로 증가). → "업로드 추격 evict" 워처(evict_watcher.py, PID기반 종료) 병행 실행하나 업로드 병목으로 효과 제한. 사용자 결정: 그대로 수집 완료(디스크 22GB 여유로 최종 17.5GB 안전). iCloud 디스크절약은 며칠 백그라운드 업로드 후 실현.

- **수집 일시중단(사용자 결정)**: 디스크 여유 13GB→완료시 ~7GB 우려로 518/762일에서 정지(PID 49657 kill). 재개 가능 설계(적재분 skip).
- **iCloud 업로드 정체 진단**: bird 데몬 CPU 94.7%(작동 중)이나 업로드 속도가 느려 518개 중 19개만 업로드완료(evict 가능), 499개 업로드 대기. evict는 업로드 끝난 만큼만 가능 → 시간~며칠 소요 가능. evict 워처 독립모드 재실행(PID .evict_pid, 수집종료 무관 계속).

### 남음 (수집 일시중단 — evict/업로드 대기 중)
- **업로드·evict 진행 대기**: bird가 14GB 백그라운드 업로드 중. 로컬이 충분히 비면(여유 회복) 수집 재개(collect_migration_streaming.py, 적재분 skip하고 519일~ 이어감).
- **수집 완료 후**: finalize_migration.py로 검증·_schema.json. dc에 생활이동 _data_registry.md 등재정보 제공.
- **당근마켓텍스트**: ToS 보류로 대기(합의 불투명). 단독진행 금지.

## 사용할 스킬
- team-inbox (peer 통지·합의)
- write-task (작업 패킷 갱신)

## 산출물 경로
- 공유 DB: `project/umc/data/compressed_db/{living_pop_dong,rental_tx,dim_adm_dong,dim_inflow_region}/`
- `.context/db-infra/convert/` (convert_living_pop.py, finalize_schema.py, convert_dong_mapping.py, convert_rental_tx.py)
- `.context/db-infra/{01,02,03}_*.md` (결정·인터페이스 문서)
