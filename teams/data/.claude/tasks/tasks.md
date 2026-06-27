# 팀 작업 — data 팀

> 운영 모델(2026-06-27 거버넌스): 이 보드는 **팀장(data-lead)이 단독으로 큐레이션**한다.
> 메일박스(team-inbox)에 들어온 작업을 팀장이 claim·분류해 아래 워커별 섹션에 배분하고,
> 워커는 자기 섹션을 read-only로 보고 수행한 뒤 `post --to-team data`로 팀장에게 보고한다.
> (워커는 메일박스를 직접 read/claim하지 않는다.)

## 상태
진행 중 — 메일박스 분류 유지(data-lead). phase00 모델 식별 불일치 = **dc 직접 실측으로 종결**(정본 경로=Claude Sonnet phase00 수동, 'gpt-4o-mini'는 코드 미보존 보조 워크플로우로 강등). de 회신 대기 불필요. → **data-lead 후속 단일창구 처리 예정: (a) write-lead에 phase00 확정값 재회신(write 대기점 해소), (b) review팀 독립대조 게이팅 해제 판단.**
현 임계경로(불변): inference-runner A-1(e6085772) 산출 → data-engineer v8 사이드카 재개 차단 해소.

## 워커별 작업

### data-engineer
- [확정] **P0/W1 정의충돌 해소(팀장 결정)**: 현 P0/W1 실행대상 = **생활이동(OD) 인프라(실행가능분)**. '당근 원문 압축DB화'는 danggeun-scraper ToS 보류로 **단독진행 금지 유지**(ToS 보류 해제 전 미실행). 보드 표기를 생활이동 인프라로 정정.
- [진행] **생활이동(OD) 수집 재개** — 518/762일 정지분 백그라운드 재개, 소스 스모크 PASS. 진척 **580/762일(남은 182일, fail=0, ~30분 내 완료 예상)**. 완료 시 finalize_migration.py로 762일 전수 검증·_schema.json 생성 후 dc에 _data_registry.md 등재정보 제공. 완료/실패 추가 보고.
- [사용자 결정 대기] **iCloud 업로드 미동작 발견** — 적재 디렉토리가 iCloud 동기화 존 미등록(brctl 'Client zone not found'). evict 워처의 '업로드완료' 로그는 거짓 판정, 518일분 14.12GB 전부 로컬에만 물질화(**데이터 손실 없음**). 디스크 여유로 완주는 가능(완료 시 ~17.5GB 로컬 영구점유). 클라우드 백업 원하면 존 등록 별도 필요 = **사용자 결정 사안** → 임의 변경 금지, 지시 대기. (data-lead가 사용자에 에스컬레이션 예정.)
- [통지] **phase00 실측은 dc가 직접 실측으로 종결, 추가 실측 불요** — de 진단(Claude Sonnet)이 보존 코드와 정합 확인됨. phase00 sha256 67b4c4f6… de 전달값=dc 실측값 교차검증 완료.
- [대기·차단됨] v8 model_id·시드 사이드카(run.json)·§7.2 안정성 v8 행 = **inference-runner A-1(e6085772) 산출 의존**. 산출 통지 시 즉시 재개 가능 상태로 대기. (현 전달 v7 기준·수치 불변 정합 확인됨.)
- [참조] 생활이동 iCloud 적재 정책 — 재현성 가드레일 명시·소비 전 다운로드 보장 규약 준수.
- [참조] 당근 원천 20컬럼 스키마 계약(danggeun-scraper) — 기존 raw 한정·신규수집 없음, Parquet 전환용(ToS 보류 해제 시).
- [완료] 패킷 dfc9ae89 R1·R2 두 갈래 완료·전달. data-lead 종결 승인 수령 확인 → data-engineer 쪽 종결 처리(추가 R1 요청 없음).
- [추적] DATA_ETHICS §4 ToS·IRB·robots 미확인 분리 = write 확정 서술 금지 조건 유지(data-lead 미확인 추적 등록).

### data-curator
- [완료] **phase00 모델 실측 종결** — text-preprocessing/src/phase00_sample_for_claude.py 직접 Read·해싱(작업경계 내 /Users/ujunbin/project/umc)으로 API 호출 코드 0건 확인 → 키워드 발견 모델 = **Claude Sonnet 수동(별칭)** 확정 종결. 'gpt-4o-mini'(MASTERPLAN)는 코드 미보존 보조 워크플로우로 강등. 부수: phase00 sha256 67b4c4f6… §G 일치 교차검증, 층화표집 시드 고정(random_state=round×42) 신규 확인.
- [완료] 부록 마스터 갱신 — REPRODUCIBILITY-APPENDIX.md §A(단계0 Claude Sonnet 수동·시드)·각주¹/¹ᵃ·§G 식별주석·§3.2.4 정합문 **확정 서술 전환** → mw 부록 확정서술 차단 해제. (미세 정정: 각주¹·§G 실측 확정일 2026-06-27→**2026-06-28**, 내용 불변·날짜만. §G 헤더 신설일 06-27 보존.)
- [완료] **§G 해시 5종 전수 dc 직접 재해싱 — 전부 일치 확정** — phase00 67b4c4f6…/phase03 8ec34da4…/phase01 1eb90fe0…/코드북 v7 2cf232e7…(커밋 fff4127 시점 record_codebook_hash.py 정규화 재계산·단순 파일해시 아님)/커밋 fff4127(HEAD). 이전 'phase00 1건만 검증·나머지 전사값' 상태 해소 → §G 박제는 전사 신뢰가 아닌 dc 독립 재해싱 검증 사실. mw 부록 박제 시 추가 재해싱 불요.
- [완료·잠정] **코드북 v8 해시 신규 포착** d42dc858… — 현 정본 워킹트리 umc_classifier.md가 이미 v8 갱신(prompt_version umc_classifier_v8_20260627·codebook_version v8·record_codebook_hash.py --check OK) = inference-runner W4(60c3f713) 워킹트리 반영분 추정. ★W4 산출 통지·정본 마킹 이전 **잠정 단서로만 부록 기록**(본문 박제는 v7 2cf232e7…만 유지). v8 정본 등재는 W4 통지 + v8 *.run.json 사이드카(A-1 e6085772 후) 시점에 dc가 registry §7.1 v8 슬롯에 채움.
- [팀장 승인] **review팀 독립대조 게이팅 해제** — aa3a6c9b 조율의 전제('dc 직접 실측 불가')가 실측으로 반증됨. de 회신 대기 불필요 → 게이팅 해제. (data-lead가 review 전달 시점·경로 단일창구 처리.)
- [대기·인계수신] **vandeursen2015vandijk 서지오류 교정 협업**(scout-lead 인계 9f425294). citekey가 가리키는 제목 vs DOI 실물 논문 불일치 → refs.bib 교정 판단(dc·mw 공동소관, paper-scout는 증거조사 입력만 담당·교정 미실행). **증거표(현citekey/제목/DOI/DOI실물제목/권고교정안) 미도착** → scout-lead 재전달 시 착수. 서지 직접수정은 증거표 근거 확보 후 진행(우리 팀 P0/W1=당근 미실행이므로 당근 재분류 보류게이트는 data측 비활성).
- [완료] 패킷 dfc9ae89 R1 §7 재현성 명세 신설 + R1 보조분 §7.4 내재화 합류(§G 박제).
- [대기·불변] v8 model_id·시드 run.json·§7.2 v8 행·잔여 해시 = inference-runner A-1(e6085772) 산출 후 등재(인계 슬롯 유지). 잔여 해시는 동일 트리라 mw 박제 시 1회 일괄 재해싱 권장.

### inference-runner
- [진행·임계경로] **A-1 재실행**(data-lead 패킷 e6085772) — C-E 223건·guard on/off ablation·EB 재실행. ⚠️ 산출(v8 model_id·시드 사이드카·§7.2 v8 행)이 **data-engineer 재개의 차단 의존** — 완료 시 data-lead로 통지하면 data-engineer 즉시 재개.
- [진행] **W4 umc_classifier 코드북 v8 갱신**(data-lead 패킷 60c3f713) — C-M-O 신규필드·정보차단 보존·버전박제. **[교차확인 권유]** W4 코드북 v8 해시 박제 시 dc 부록 잠정값 **d42dc858…**(현 워킹트리 기준)과 일치하는지 교차 확인.

## 목표
편집부 Major Revision/2차 Reject&Resubmit 대응(.project/goals/) 중 데이터팀 소관:
재분류 파이프라인(v8)·재현성 명세(R1)·데이터윤리(R2)·A-1 멀티에이전트 검증.
