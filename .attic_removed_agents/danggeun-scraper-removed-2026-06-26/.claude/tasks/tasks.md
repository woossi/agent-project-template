# 작업

## 상태
동결 (크롤링 미실행 고정 — 사용자 결정: 현 raw로 투고. 산출 보존, 다음 지시 대기)

## 목표
당근 게시글 크롤링의 구조를 점검·재검토하고, scrapling 기반 전국 전수 크롤러를 재구축하며, 수집 적법성(ToS)을 검토해 UMC §3.3 원천 수집 계층의 재현성·거버넌스를 확립한다.

## 배경
UMC 3.3절 하이퍼로컬 플랫폼 신호 분석의 입력(당근 동네생활 게시글 131,792건)의 원천 수집 계층 책임. 수집 로직·스키마·커버리지·재현성 점검과 크롤러 재구축이 목표.

## 입력
- 원천: /Users/ujunbin/project/umc/analysis/part 3/data/raw/daangn_chunk_*.csv (24파일·1,305,675행)
- 파이프라인: analysis/part 3/01_text_preprocessing/ (phase00~03)
- 분류산출: analysis/part 3/02_bayesian/data/processed/03_umc_classified.csv (131,792)
- 외부 크롤러: github.com/ITU-project-team/daangn-crawler (공개 정화본 ce14003)
- 당근 ToS(시행 2026-01-09)·개인정보처리방침(시행 2026-03-27)

## 기대 산출물
- 점검 보고서 6종 + 종합 인덱스 (.context/danggeun-crawl-audit/00~06)
- scrapling 재구축 전국 전수 크롤러 (.context/danggeun-crawl-audit/scrapling_crawler/, 코드·테스트·README)
- B/C 스키마 계약·manuscript 핸드오프 발신

## 사용할 스킬
- team-inbox: peer 메시지 발신·수신·ack
- reminders-team-bridge: 진행상태 annotate
- write-task: 현재 작업 패킷 갱신

## 사용할 서브에이전트
- (없음) 직접 실행. MCP(scrapling get·github·fetch)로 검증·점검 수행.

## 필요한 결정
- 댓글/전국 크롤러 대량 라이브 실행 여부 → 당근 ToS 사전 서면 동의 확보 필요(사용자·orchestrator 결정 영역). 현재 실행 게이트.
- B/C 스키마 합의·manuscript 기재 확인 → 타 에이전트 회신 대기.

## 위험
- ToS: 사전 서면 동의 없는 자동 수집은 명시 금지(저작권법·정보통신망법 소지). 무동의 대량 실행 미수행 유지.
- 재현성: 외부 크롤러 공개 정화본(14컬럼)≠실수집(20컬럼), 수집일자 로그 부재.
- 개인정보: 닉네임·작성자 거주동(개인위치정보) — 가명처리·최소수집으로 완화하나 수집 자체 ToS 제약.

## 검증
- 원고 §3.3.4 수치 트리 직접 대조: 시간범위·후보149,733·분류131,792·관련성 Y7,136/N122,509/?2,147 전수 일치
- 크롤러 테스트: python3 test_{parse,nationwide,edge}.py → 3/0 통과
- scrapling 라이브 실측: 서울·비서울·삭제글·엣지 케이스 end-to-end

## 완료 기준
- 점검·재구축·ToS검토 산출 완성·자산보존 (달성)
- B/C 스키마 계약·manuscript 핸드오프 발신 (달성)
- 타 에이전트 회신 처리 및 합의 (대기 중)
- (조건부) 적법 동의 확보 시 크롤러 단계 실행 (게이트)

<!-- component-contract:start -->
## 계약 연계

- 작업은 에이전트가 실행하는 가장 작은 작업 단위이며, 에이전트가 자동으로 기록하고 갱신한다.
- 작업 패킷은 현재 상태(목표, 입력, 검증, 완료 기준)만 담고, 진행 로그와 handoff는 `.context/`에 둔다.
- `사용할 스킬`에는 필요한 능력과 절차를 참조로 적는다. 절차를 복사하지 않는다.
- `사용할 서브에이전트`에는 역할, 담당 범위, handoff 위치를 적는다.
- 결과는 작업의 검증과 완료 기준으로 되돌아온다.
<!-- component-contract:end -->
