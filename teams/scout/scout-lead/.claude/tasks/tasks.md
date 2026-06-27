# 작업

## 상태
조정 중 (자율 운영)

## 현재 할당 (paper-scout)
1. **선행 인용조사 3건** (orchestrator 선행지시 — 당근 재분류 v8 무관, 지금 가능)
   - A1. 잠재기제 '층위분화' CR 이론근거 (실재층위 내 지역/문화/역사 하위층위)
   - A2. realist evaluation × 인과추론 결합 (인과추론=보조 검증장치)
   - A3. 역행추론 경쟁가설 상대비교 방법론 (IBE 상대적 설득력)
2. **yeung2024 명시확인 1건** (mw 요청) — refs.bib 서지 정확성 + ch2:35 인용 정합성

### 신규 배정 (paper-scout — idle 가용 통지[msg 01782572622624746000]에 대응, 즉시 착수 지시)
3. **B3. 신규 ref 등록 전 refs.bib 전수 선조회** [최우선·게이트무관] — lawson1997/habermas1987이 refs.bib에 이미 존재하는지 + 동일 문헌이 다른 citekey로 중복 등록돼 있는지 전수 조회. 결과로 '신규등록 가능/기존citekey 재사용' 판정 회신. 후속 ref 등록의 차단요인 선해소.
4. **B1. perkins1987 본문 기관접근 재시도** [2순위·게이트무관] — Scopus/ILL/OA 재시도로 원문 확보. 성공 시 ch2 해당 인용 원문근거 채움(verbatim+근거페이지). 실패 시 '접근경로별 실패사유' 정직표기 후 mw에 채택 재판단 입력으로 회신.
5. **vandeursen2015vandijk 서지불일치 증거정리** [조사입력만 — 교정은 mw·data-curator 공동소관] — citekey 제목 vs DOI 실물(Crossref) 불일치 내역을 증거표로 정리(현 citekey / 제목 / DOI / DOI실물제목 / 권고 교정안). 교정 실행은 하지 말고 증거만 data-curator·mw에 인계 준비.

### 후속 대기 (요청 시 착수)
- **B2. neighbor wynn2012williams·fletcher2017 primary 본문 확보** (현재 초록2차만 — 확보등급 보강. mw가 본문 인용 강도 올릴 때 트리거)

## 처리 완료 (조정)
- data-curator 회신 ack: PDF 매칭 영구산출물 오매칭 0건 확정(이미 정본), firebaugh 톤 정정 완료 → scout 우려 해소, 추가조치 불요
- orchestrator 선행지시 ack → paper-scout 위임 패킷으로 전환
- mw yeung2024 요청 ack → 위임 패킷에 포함
- 위임 라인 건강 확인: paper-scout 패킷(01782561798919417000) unclaimed(=대기 정상), 입력메시지 3건(data-curator/orchestrator/mw) 모두 consumed, 미리알림 scout 항목 등록 완료
- [거버넌스] new_worker 신호 'scout:paper-scout' decline 처리(scout-lead=팀 owner). 근거: scout=팀장1+생산자1 설계라 load30 vs mean15는 구조적 필연이지 백로그 폭증 아님. 결정 기록: .project/promotions/decisions/new_worker__scout_paper-scout__7379bb7d.json. 재평가 트리거: paper-scout에 동시 위임 다건 적체 시 data-lead에 add-subteam 요청.
- **[ms 그라운딩 완료 수령·ack] paper-scout msg 01782572369471039000(완료보고)+01782572441150301000(상태확인 중복방지)** claim→ack. ms 요청(59561f1e) 산출물 검증 끝:
  - 2장 인용 31/31 원문근거 충족 (CSV ch2-citations-for-ps 뒤 3열 + 배치 batchA/B/C 입력 10+10+11 전부 대응). 확보등급: verbatim 7건(eastwood2014/2019·schurz2008·yeung2024·vangrootel2017·robeyns2005·lim2025)/초록 verbatim 다수/단행본 스니펫+2차교차 4건. 미확보는 전부 '원문 미확보' 정직표기, 창작추정 없음.
  - 핵심어 3개 정의 출처(handoff ch2-keyword-definitions): 준규칙성=Lawson1997 p204(Crossref검증, lawson1997 신규부착 권고)/생활세계흔적·집계흔적=Habermas TCA Vol2 1987 p154(본연구 신조어, 정직표지)/지역역량=Sen1985·Robeyns2005 p94,96·Lim2025 p21(근거체인 완비).
  - 종합 핸드오프 handoff ch2-citation-grounding-summary(mw 직접전달 준비됨).

## 거버넌스 인지 (scout 비-owner — 처리 안 함)
- project_skill 신호 'scout+write'(paper-scout↔mw 핸드오프 42건) 등은 프로젝트 owner(orchestrator) 권한. scout-lead는 저작 불가. owner 저작 시 scout↔write 패턴 제공 가능.

## 게이트 인지
- 당근 재분류 진행 중(사용자 확정 2026-06-27). 본문 수치/서지 직접수정 보류. scout 조사·검증 작업은 게이트 무관.

## Cross-team 전달 (scout-lead → 타팀 인계, 별도 메시지 발신 예정)
- **→ mw(write팀):** ms 그라운딩 완료. 종합 핸드오프 handoff ch2-citation-grounding-summary 전달. 본문 LaTeX 인용 삽입은 mw 소관. 질의 응답: ① lawson1997 신규 부착(준규칙성 용어 소유자=Lawson) ② 생활세계흔적/집계흔적 — 어원 표지만 vs 이론틀 도입 결정 필요(mw 판단 대기) ③ wynn2012williams·fletcher2017 primary 미확보(필요 시 paper-scout B2 트리거).
- **→ data-curator(data팀):** vandeursen2015vandijk 서지오류 교정 협업 필요 — citekey 제목과 DOI 실물 불일치(교정 필수). mw와 공동.

## 대기
- 위 cross-team 전달 발신 후 응답 대기. paper-scout 후속(B1~B3)은 트리거 시 위임.
- orchestrator에 완료 상황 통지(선행지시 분 마무리 보고).
