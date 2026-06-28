# 스킬: data-artifact-pipeline

## 사용 시점

data 팀(data-engineer·data-curator·inference-runner·data-lead) 안에서 **원천 데이터 → 추론 재실행 → registry 등록 → cross-team 전달**로 이어지는 산출물 파이프라인을 한 번 흘려보낼 때. 구체적으로:

- 원천 raw를 쿼리가능 압축포맷(parquet/duckdb)으로 전환·스키마화해 다운스트림에 넘길 때.
- 그 위에서 분류·판정·EB 같은 추론을 (재)실행해 산출물을 생산할 때.
- 생산된 산출물을 `.project/data_registry/`·`.project/runs/`·`.project/evidence/` 정본 후보로 큐레이션할 때. worker/team 단계에서는 canon JSON을 직접 만들지 않고, owner 승인 후 프로젝트 최종 JSON으로만 닫는다.
- 등록 완료분을 write 팀(원고 내재화)·review 팀(독립 검증)으로 넘길 때.

이 스킬은 그 핸드오프 사슬(누가 누구에게 무엇을 넘기는지)의 **반복 구조**를 고정한다. 한 작업 단위의 진행상태는 미리알림(`reminders-team-bridge` annotate)에, 에이전트 사이 메시지는 `team-inbox`에 둔다.

## 목적

data 팀의 산출물이 손실·재현불가·외부저장소 의존 없이 원천에서 cross-team 소비처까지 흐르도록, 단계별 소유권·핸드오프 시점·필수 메타데이터를 한 절차로 고정한다. 재현성(R1)·정보차단 경계·수치 정본 조율을 매번 다시 합의하지 않는다.

## 계약

- 읽는 입력: 작업패킷(`team-inbox`의 `quality_gate.axes`·정지조건), 원천 raw(작업경계 `project/umc` + iCloud `umc-compressed-db` 내), 기존 `.project/data_registry/`·`.project/runs/`·`.project/evidence/` 정본, 소비 규약(`README_consume.md`).
- 만드는 출력: 압축DB/스키마(data-engineer), 추론 산출물+메타(inference-runner), 팀 단계 evidence candidate packet(비정본 Markdown/handoff), registry 등록 제안·표/그림(data-curator), cross-team 전달 메시지(`post --to-team write|review`). 최종 구조화 JSON은 owner 승인 뒤 `.project/evidence/*.json` 등 프로젝트 canon에만 쓴다.
- 쓰면 안 되는 위치: 타팀 작업경계(write=`research/UMC` 직접 편집, review 산출). `/Users/ujunbin/article`은 읽기 전용 보존. 공유 store는 Read/Edit/Write 도구가 아니라 `team_inbox.py`·`reminders_bridge.py` CLI로만 접근(path guard 우회 정상 경로).

## 입력

- 안정적 정체성(`export CLAUDE_AGENT_NAME=<이름>`). 미설정 시 `main`으로 붕괴.
- 단계 소유권 매핑(고정):
  - **data-engineer** — 원천 압축·스키마·프롬프트 전문 추출(외부저장소 의존 제거).
  - **inference-runner** — judgment-synthesizer C-E·guard on/off ablation·EB 등 추론 재실행(생산자).
  - **data-curator** — registry 등록·버전관리·큐레이션·표/그림·원고 내재화 가능 형태화.
  - **data-lead** — 분해·위임·품질원장·cross-team 전달 조율(직접 생산 안 함).
- 각 산출물에 박제할 메타: 모델버전·시드·프롬프트 전문·코드 ref·sha256(R1 치명, '현재 원고만으로 심사' 기준).

## 절차

1. **분해·위임(data-lead).** 작업패킷을 `team_inbox.py post --to-team data`로 발송하되 본문에 담당 생산자를 명시하고 `--quality-gate '{"axes":[...],"kind":...}'`로 정지조건 축을 박는다. 미리알림(`umc-data`)에 같은 작업을 priority로 추가(두 채널 동기화).
2. **claim(생산자).** 생산자가 기동 후 자기 소관 패킷을 `claim`(원자적, 1명만). inference-runner는 사용자가 `export CLAUDE_AGENT_NAME=inference-runner` 후 기동해야 활성 — 그 전까지 패킷은 inbox 대기.
3. **원천화(data-engineer).** raw → 압축포맷 전환·스키마화·dbId 인덱싱. 보존 필수 컬럼·클리닝(DELETED/BLOCKED·중복) 카운트 보고. 개인정보 컬럼(writer_*)은 마스킹/제외/접근통제. iCloud 외부 데이터셋은 소비 전 `brctl download` 보장 규약을 `README_consume.md`에 등재.
4. **추론 재실행(inference-runner).** 원천·스키마를 입력으로 추론 (재)실행. 정보차단 경계 보존(C-M-O 단서는 I_J 단계에서만, I_R에는 텍스트+기본메타만). 산출과 함께 모델버전·시드·프롬프트·코드 메타를 남겨 registry 등록 가능 형태로.
5. **registry 등록·큐레이션(data-curator).** 산출물을 `.context/evidence-packets/` 또는 팀 `.context/evidence-candidates/`에 비정본 packet으로 정리한다. 버전·시드·프롬프트·해시·source_data/run_id/evidence 후보를 명시하되, `.project` canon JSON은 owner 승인 전 직접 쓰지 않는다. 외부저장소 의존 제거(원고 내재화 가능 형태). 영향받는 표/그림(ICC·z_shift·ablation) 갱신. 그림은 `figure-designer`/`gis-figure-designer`에 1건씩 위임.
6. **검증 핸드오프(→review).** 산출물을 `post --to-team review`로 넘겨 stats-validator 독립 수치 대조·인간코딩 IRR 검증. verdict는 `--verdict`+`--work-ref`로 추적.
7. **원고 내재화 핸드오프(→write).** 재현성 명세·윤리 자료·재분류 결과를 `post --to-team write`로 넘김. ★분류 출력구조 변경이 본문 수치에 영향 주면 write 팀 manuscript-steward(수치 정본 소유)와 반드시 조율.
8. **품질원장·종료(data-lead).** 도착 산출물에 `team-quality-ledger record`로 verdict 기록. 정지조건 충족분은 미리알림 `complete`, 패킷 `ack`.

## 출력 형식

- 압축DB·스키마 명세(data-engineer), 추론 산출물+메타(inference-runner), 비정본 evidence candidate packet·표/그림(data-curator). 프로젝트 최종 산출은 owner 승인 후 `.project/evidence/*.json`·`.project/runs/*.json`·`.project/data_registry/*.json`만 구조화 JSON으로 남긴다.
- cross-team 전달 메시지(write·review 메일박스에 1부), 미리알림 진행 annotate, 품질원장 verdict.

## 내부 자원

- (없음) — 절차만 고정한다. CLI는 공유 스킬 `team-inbox`(`team_inbox.py`)·`reminders-team-bridge`(`reminders_bridge.py`)·`team-quality-ledger`를 참조한다.

## 품질 점검

- 모든 산출물에 모델버전·시드·프롬프트·sha256이 박제되어 외부저장소 없이 재현 가능(R1).
- 정보차단 경계가 추론 단계에서 보존됨(C-M-O는 I_J에서만).
- 두 채널(미리알림·메일박스)이 동기화됨 — 작업이 한쪽에만 있지 않음.
- cross-team 전달이 수치 정본 소유(write manuscript-steward)와 조율됨.
- 타팀 작업경계·`/Users/ujunbin/article` 보존 위반 없음.

## 자주 발생하는 실패 사례

- **생산자가 산출만 내고 메타 누락** → registry 등록 불가·R1 위반. 4단계에서 메타 동봉을 강제.
- **정보차단 경계 누설**(C-M-O를 I_R에 노출) → A-1 검증 무효. 명세 §5 참조해 단계 분리 확인.
- **분류 구조 변경을 write에 통지 없이 진행** → 본문 수치 불일치. 7단계에서 manuscript-steward 조율 필수.
- **공유 store를 Write 도구로 직접 수정하려다 guard 차단** → 정상. `team_inbox.py`/`reminders_bridge.py` CLI(Bash 경유)로만 접근.
- **팀장이 직접 생산** → 생산자≠조율자 경계 위반. data-lead는 분해·위임·조율만.

<!-- component-contract:start -->
## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.
<!-- component-contract:end -->
