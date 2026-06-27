# Memory — agent: manuscript-steward

Private working memory (facts this agent learns while working).
Team-wide decisions and goals live in the team store (.project/memory, .project/goals).

## Durable Facts

- **★B판 명료성 정본(steward 소유 '파트 가로지르는 일관성·용어·구조·논증 정의', writer 요청 4건 회신 2026-06-27)**: 정본=`.context/clarity-canon-B-2026-06-27.md`. ①어휘 13개 정의·본거지·영문 정본화(잠재기제=붙임 generative mechanism, 잠재 구조=띄움 latent structure, 잠재 상태=띄움, 인과기제=CR 일반정의 병기없음). ②파트계약: §2=메타이론·개념 본거지, §3=절차·형식·수치 본거지, intro=명명+역할 한 문장. ③중복 정의처: 괴리=신호→§2.2(ch2:43–44), 지역역량6요소→§2.3(ch2:62–64)만(intro:11 축약). ④파트 3분할(forward 누설 차단). ★진단 카운트 정정(내 grep): 괴리107·역행추론143·잠재기제125(writer 71/72/183은 오차). **T1 위반 7건 교정표 확정**: 잠재 기제(띄움)→잠재기제 ch2:7·9·22·24·26 / 생성기제→인과기제 ch2:14캡션 / 잠재구조→잠재 구조 results:51. 본문수정=writer.
- **★본문 수치 정본 소유(orchestrator 확정 2026-06-27, team.json roles(4))**: 본문 수치·통계량 정본의 단일출처 보관·일관성·창작변형 금지 기준은 steward 소유. 정본 문서=`.context/numeric-canon-B.md`(parts_ko_B 전 본문·표 실측 채취, file:line 근거). 다른 peer(writer 포함)가 본문 수치 쓸 때 이 정본 기준, 의심 시 steward 조회. **경계: 보관=steward, 그 값이 데이터·코드와 일치하는지 독립 재현 검증=stats-validator**(보관자≠검증자). 핵심 미해결 위험 2건(정본 §9): ①중랑 연결품질 z_shift 표기분열 +1.73(results:114/appendix:87) vs 1.69(results:125)=정본 미확정·sv 검증 의뢰 대상, ②댓글 37만/187만은 후속과제 추정치(결과 아님·인용금지). 표본흐름 정본: 149,733→131,792→Y7,136 / 표적 223건→가설772(미결490/반박156/지지126)·중랑집중84.1%(106/126).
- **B판 제목 고정(사용자 확정·★변경금지, orchestrator 2026-06-26)**: "서울 자치구별 디지털 활용능력 잠재기제의 체계적 추론: 비판적 실재론적 관점에서". `umc_paper_ko_B.tex` \title 블록. 어떤 작업에서도 임의 변경 금지. 이전 제목(행정기록과 생활세계의 괴리에서…)은 이력으로만 보존.
- **B판 줄간격**: `setspace`+`\setstretch{1.2}`(사용자 요청). 본문 42쪽. 값 변경은 orchestrator 경유. 미시/체재 작업 시 유지.
- **T1 정본 확정(잠정, 사용자 최종확인 대기)**: '잠재기제'로 통일. 영문 병기는 본문 최초 등장(intro) 1곳만 `잠재기제(generative mechanism)`. '생성기제' 전 파일 0회. ch2:9는 병기 없는 '인과기제'(CR 3층위 일반정의).
- **B판 본문 변경 보류(orchestrator 2026-06-26)**: 사용자 결정(국문초록 기관규격·저자 실명/심사위원 블록·T1 최종확인) 전까지 B판 본문 추가 변경 보류. 별도 지시 없으면 현 상태 유지. → R3 캡션 등 미해결 표기교정은 다음 미시 회전에 묶어 처리.
- **glossary-B 정본(정본=`.context/glossary-B-draft.md` v2)**: B판 핵심 개념어 사전의 단일 정본은 `.context/glossary-B-draft.md`. 잠재 구조 ≠ 잠재 상태 ≠ 잠재기제(역행추론 대상) 3축 경계가 논문 전체 축. 에이전트=역행추론 주체(단계 E), 종착=정책 검증(B판 프레이밍). 안정화 후 `register-term`으로 `.project/word.json` 파생 예정. *Derive: term: 잠재기제*
- **표기규약(정본·★변경금지)**: ①`잠재기제`=붙임 정본, `잠재 기제`(띄움) 금지. 단 `잠재 구조`(띄움)는 별개 용어(latent structure)로 정상. ②영문 병기는 본문 최초 등장 1곳(`body_front_intro.tex:15`, `\emph{잠재기제(generative mechanism)}`)만. `생성기제`=동의어이나 전 파일 0회(MW 제거 완료). ③`인과기제`(병기 없음)=CR 3층위 일반정의(ch2)·F11 캡션. *Derive: preference*
- **그림 일관성 현황(정본=`.context/figures-B-consistency.md`)**: 본문 figure 11개(F1~F11) 전부 라벨↔참조 정합·이미지 실재. F11=`fig:cr-strata`(fig_cr_strata.png, CR 세 층위) 생성·연결·검증 완료(2026-06-26). R1(고아 figures_main.tex)·R2(구버전 이미지)=data-curator attic 격리·steward 검증 닫힘. **잔존 R3**: F6 캡션 "3.3절" 하드코딩(실제 §3.2) — 본문 변경 보류라 다음 미시 회전에 R3·T3·T5와 묶어 처리. 그림 생성·파일=data-curator 소유, 본문 배치·캡션·참조 일관성=steward 소유.
- **★용어 일관성 점검 패턴(steward 절차 명문화, orchestrator 지시 2026-06-26)**: 신규 개념어·표기 변경을 다룰 때 표준 절차 — ①**신규개념어 후속장 전파 점검**: §N에 도입한 개념어가 후속 장(§N+1…)·초록·캡션까지 일관 전파됐는지 grep 실측(도입만 하고 후속장 누락 빈발). ②**이형 표기 분열 탐지**: 동일 referent의 띄어쓰기·영문병기·동의어 이형(예: 잠재기제/잠재 기제/생성기제)을 grep 카운트로 분포 확정 후 정본 1형태로 수렴. ③**구조 재편 후 재실측**: §재편(MW)이 새 단락을 추가하면 정본 위반 이형이 유입되므로(예: §2 재편 시 `잠재 기제` 5곳 유입) 재편 직후 재실측 필수. ④판정은 inbox 보고가 아닌 **본문 grep 실측**에 근거(보고=검증대상 가설). ⑤본문 직접 수정은 MW 소관 — steward는 교정표(파일:라인+수정안)까지만 산출.
