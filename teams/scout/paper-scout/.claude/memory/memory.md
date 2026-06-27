# Memory — agent: paper-scout

Private working memory (facts this agent learns while working).
Team-wide decisions and goals live in the team store (.project/memory, .project/goals).
휘발성 작업 사실(신규 ref 키 누적·날짜별 실측·진행 중 미해결)은 `.context/ref-verification-ledger.md`에 외부화. 메모리는 재사용 절차/방법론만 둔다.

## Durable Facts (재사용 절차)
- **서지 대조 검증**: DOI는 doi.org cross-host 리다이렉트로 WebFetch가 한 번에 못 따라감 → Crossref REST(api.crossref.org/works/<doi>, 단일호스트)로 1차 대조. online-first vs print 연도는 CSL-JSON transform(.../transform/application/vnd.citationstyles.csl+json)의 published-print로 구분(인용 키 연도=print 게재호 기준). DOI 없는 챕터·미래게재는 독립 2차 출처로 교차확인.
- **기존 ref 자산 + ★선조회 의무**: research/UMC/refs.bib(채택 키·중복회피 기준) + parts/_newrefs_map.md + citekey_map.md를 새 검색 전에 먼저 본다. ★채택/등록 권고 직전에 후보 키 전수를 refs.bib에 grep 재선조회(엔트리수 추정으로 '미존재' 단정 금지). 유사키·표기변형(저자 다른 철자 Antonio/Ángel·연도 print/online myovella2020/2021·특수문자 깨짐)까지 패턴에 포함. 절차·품질점검·실패사례 3계층이 scholarly-evidence-search 스킬에 반영됨(실측 교훈: 서론 7키 중 3키 채택직전 grep 누락→오판, 후보 多일 때 빠뜨리기 쉬움).
- **두 엔진 + snowball**: Consensus=키워드, Scholar Gateway semanticSearch=의미 → 교차해야 정전 안 놓침. 중요 논문은 인용 네트워크(Crossref works/<doi> reference=후방, 피인용=전방 snowball)가 키워드보다 신뢰도 높음.
- **내부 RAG**: obsidian-vault MCP(/Users/ujunbin/knowledge, ~3,500노트: 01.문헌·02.개념·03.개인범주화·04.확장/project/UMC). 본문 설계의 기원·계보가 여기 정리돼 있을 때 많음(예: 01.문헌/01.3 보고서/ITU_2023.md = §3.1 측정설계 min-max+동일가중+6차원 직접 기원). ★내부 노트 서지는 오류 가능(실측: Price_2020노트 저자 오류=실제 Ritz, Waite노트 연도·권·페이지 오류) → refs 등록 전 Crossref verbatim 대조 필수.
- **로컬 PDF 라이브러리** = /Users/ujunbin/article/ (~1063개, '저자_연도.pdf' Zotero 형식). 본문 확보 최우선 경로(합법·빠름)이나 커버리지 부분적('있으면 최우선, 없으면 외부'). ★기본 작업경계 밖이라 guard가 Read 차단 → data-curator에 AGENTS.md allow + agent-workspace.json defaults.allow 추가 요청해야 사용(요청 발신 완료). Read 도구가 PDF 지원.
- **PDF/본문 확보 계층**(fetch-paper-fulltext): 로컬 PDF → OA(WebFetch; CC BY면 arXiv 저자본 arxiv.org/html/<id>가 봇친화) → 페이월/Cloudflare(402·403·리다이렉트)는 scrapling stealthy_fetch(solve_cloudflare=true·network_idle·timeout≥60000)로 다수 통과 → Scopus(연세계정, 에이전트 직접로그인 불가→사용자 세션쿠키 scrapling 주입 또는 사용자 폴백). 쿠키 휘발사용·저장금지, 본문 전문 복제 금지(발췌만). ★Cambridge Core는 봇차단(404/400/500)이라 OA여도 arXiv 저자본이 확실.
- **검증 질문 유형 판별**: '관행·서술방식·방법절차·정확인용'은 abstract로 답 못함→본문 필수(fetch-paper-fulltext). 서지정확성만이면 Crossref로 충분.
- **PDF→텍스트 추출 환경(설치 완료, 재설치 불요)**: Read 네이티브 PDF(`pages:` 범위) + pdftotext·pdfinfo(poppler, verbatim grep) + PyMuPDF(fitz)·pdfplumber(표·2단 조판) + tesseract 5.5.2 OCR(163 언어팩·kor 포함, 스캔본용). 별도 MCP 불요 — 로컬 CLI가 더 빠르고 가벼움. **인용 근거는 초록이 아니라 정확한 본문 내용 기반**(사용자 결정 2026-06-27, 전수 모드). 번거로운 본문 처리(확보→전수 인용근거 추출→mw 핸드오프)는 서브에이전트 `fulltext-grounder`(.claude/agents/)에 위임 — 인용 키 목록+본문 자리를 입력으로 받아 핸드오프 표(.context/agents/fulltext-grounder/) 산출, 본문 삽입은 mw 소관.
- **B판 맥락 + 신규성 방어 프레임**: B판 = 석사 학위논문(CR 생성기제 탐색), 이론장 = '6단계 논증=Research_Map'(6단계↔섹션 매핑은 .project/memory `research-map-6-step-argument-x-bpan-sections`). 신규성 귀속 방어 = 기여를 '통합 자체'가 아니라 '정보차단 멀티에이전트 역행추론 절차화'로 좁히고, 차별화 대상을 정직 명시(억지 동일시·과대 귀속 금지). 키 누적·진행 중 항목 = `.context/ref-verification-ledger.md`.

## 운영 원칙 (회고 채택, 사용자)
- Derive: preference — 근거 탐색 시 내부 자산(obsidian-vault·작업경계 RAG)을 외부 학술검색보다 먼저 조회한다.
- Derive: preference — 대상 본문을 처음 읽을 때 인용이 빈약한 지점(단일/무인용 정당화)을 즉시 갭으로 진단하고 쿼리를 그에 맞춰 설계한다.
- Derive: preference — 중요 논문 탐색은 키워드 한 엔진에 의존하지 않는다(기존 ref 선조회 + 두 엔진 교차 + snowball).
- Derive: preference — 검증이 abstract로 안 되는 유형이면 본문을 직접 확보해 문장 단위로 대조한다. abstract를 본문 확인인 척 쓰지 않는다.
- Derive: preference — 채택/등록 권고 brief에 'refs.bib 전수 선조회 이행'을 한 줄로 명시해 가시화하고, grep 패턴에 유사키·표기변형까지 포함한다(서론 3키 오판 재발 방지).
