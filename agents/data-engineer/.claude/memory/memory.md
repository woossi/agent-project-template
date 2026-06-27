# Memory — agent: data-engineer

Private working memory (facts this agent learns while working).
Team-wide decisions and goals live in the team store (.team/memory, .team/goals).

## Durable Facts

### 압축 DB 인프라 — 확정 포맷·규약
- **저장 포맷 = Parquet + ZSTD level 9** (dictionary on) 단일 선정. duckdb는 *옵션 뷰 계층*(원천 저장 포맷 아님). 결정 요인: 소비측(data-curator)이 pyarrow/pandas로 추가설치 없이 즉시 읽음 — 시스템 파이썬이 externally-managed라 duckdb는 venv 필수라서 진입장벽이 됨. `Derive: term: ZSTD-9`
- **ZSTD-9가 균형점**(실측): 9 이상은 압축이득 미미(46.5→45.3MB)한데 쓰기시간 급증(1.15→5.29s). zstd-1=2.73x ~ zstd-22=3.96x 곡선에서 9가 압축/속도 무릎.
- **파티션키 = `year_month` 단일**(hive, **string으로 명시**). 자치구·동 파티션은 동 424개×월수로 과분할(small-file) → 배제. 동 필터는 파일 내 컬럼 필터로 충분(쿼리 6~7ms). `Derive: term: year_month`
- **hive 파티션 함정(검증됨)**: 파티션 컬럼은 디렉토리명에서 타입 자동추론되어 `year_month`가 int32로 캐스팅됨. 운영 dataset/소비 코드 모두 `partitioning`에 **명시 스키마(string)** 지정 필수.
- **코드성 컬럼은 string**: `base_date`(YYYYMMDD), `time_slot`(00~23), `adm_dong_code`(8자리). 선행0 보존·조인 안정성 때문. 인구수 컬럼은 무손실 우선 `double`(float32 다운캐스트는 압축여지 후보로 보류). `Derive: term: adm_dong_code`
- **소비 계약 = `_schema.json`**: 각 데이터셋 디렉토리에 컬럼·타입·코덱·root_path·known_issues 동봉. living_pop은 `_validation.csv`(월별 행수·합계·pass/fail)도 동봉. `Derive: term: _schema.json`

### 검증 규약 (확정)
- **3중 무결성 검증을 변환과 동시 수행**: ① 행수==CSV 데이터행수, ② total_pop 합계==CSV 합계(오차<1e-3), ③ 고유 동수·시간대·날짜==기대치(일수×24×424). + 라운드트립 + 독립 CSV 진실값 대조. living_pop 39/39 PASS. `Derive: term: 3중 무결성 검증`
- grain(행 단위) = `(base_date, time_slot, adm_dong_code)` = 일×24시간대×424동.

### 데이터셋별 확정 사실 (공유 DB: `project/umc/data/compressed_db/`)
- **living_pop_dong**: 39개월(202301~202603 연속), 12,048,308행, 4.60GB→1.36GB(3.37x). 파티션 `year_month=<YYYYMM>/part-0.parquet`.
- **rental_tx**: 600,000행/10개월(202506~202603), 8.3MB. SNAPPY 6chunk→ZSTD-9 10파티션 재기록. CGG_CD↔dim_adm_dong.sigungu_code 조인.
- **dim_adm_dong**(424행): 동코드↔동명·자치구 조인키, sigungu_code 파생. living_pop 커버리지 100%.
- **dim_inflow_region**(96행): 생활이동 출발지 차원.
- **seoul_migration_od**(생활이동, 수집중): 1일=CSV 155MB·236만행→parquet-zstd9 22.9MB(6.76x). 762일 추정 CSV~118GB·parquet~17.5GB. iCloud Drive 적재(로컬 28GB 제약 우회).

### dedup·정밀도 단차 (소비측 필독)
- **소스 dedup 규칙**: 202301~202404(16개월)=03.Test-for-inference(영문헤더, 소수1자리 반올림, 이 기간 유일소스), 202405~202603(23개월)=02.baysian(한글헤더·BOM·trailing comma, 풀 정밀도). 02.=03.은 동일원천의 정밀도/포맷 변형(03.=02. 소수1자리 반올림). tmp/202509는 02.와 md5 동일 → 무시.
- **정밀도 단차 경고**: 202404↔202405 경계에서 정밀도 단차(03. 반올림 vs 02. 풀정밀도). living_pop `_schema.json` known_issues에 severity=warning·affects=[stats-validator,data-curator] 명시. 시계열 합산·미분 시 주의.
- **변환기는 소스별 다른 CSV 포맷을 흡수**(02. 한글/따옴표/BOM/trailing vs 03. 영문/순수)하고 단일 통일 스키마(영문 스네이크) 출력.

### 알려진 이슈 (변환 손실 아님 — 원본 자체)
- 202509 결측 76행: 원본 누락(20250918 00시 57동, 23시 19동). 변환 손실 아님.
- 202509 헤더 CP949 손상: 데이터행 순수 ASCII라 latin-1 디코드로 흡수, 값 무영향.

### iCloud 스트리밍 적재 교훈 (생활이동)
- **스트리밍 수집 패턴**: 일자별 다운로드→추출→parquet→iCloud 적재→ZIP/CSV 즉시삭제(피크 로컬~190MB)로 118GB 원천을 로컬 28GB 제약에서 처리.
- **brctl evict 제약(실측)**: 업로드 완료 후에만 evict 가능(-2008). 업로드가 수집속도를 못 따라가면 로컬 점유가 계속 증가 → "업로드 추격 evict 워처"는 업로드 병목으로 효과 제한적. iCloud 디스크절약은 즉시 실현 안 되고 백그라운드 업로드 며칠 후 실현.

### 역할 경계 (확정)
- data-engineer = 원천 데이터 압축 저장·스키마·쿼리 인프라 계층 **소유**. 분석결과·그림·데이터 레지스트리·팀 컨텍스트 큐레이션은 data-curator 소유(de가 만든 압축 DB를 dc가 소비). 집필(원고)은 manuscript-writer/steward 소관 — **academic-writing 스킬은 de 역할과 무관**.

### Open
- 인구수 컬럼 float32 다운캐스트 무손실성 검증(추가 압축 여지) — 보류.
- 생활이동 수집 일시중단(518/762일, 디스크 여유), 업로드·evict 대기 후 재개. 완료 후 finalize_migration.py 검증·_schema.json, dc에 _data_registry.md 등재정보 제공.
- 당근마켓텍스트: danggeun-scraper ToS 보류로 대기, 단독진행 금지.
