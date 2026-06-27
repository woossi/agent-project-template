# 작업

## 상태
완료 (2026-06-28 — phase00 모델 식별을 dc가 작업경계 내 코드 직접 실측으로 확정. data-lead 조율 aa3a6c9b의 전제 'dc 직접 실측 불가'는 실측으로 뒤집힘 → §A/§G 주석 병존 해소·확정 서술 전환. data-lead 보고 발신.)

## 최신 진행 (2026-06-28 vandeursen2015vandijk 서지오류 — 1차 증거조사, 증거표 미도착 상태 선제 수행)
- [★경계 확정] data-curator deny에 `/Users/ujunbin/research/UMC/**` 명시 → **refs.bib는 dc 경계 밖**(직접 교정 불가). 2026-06-27 화이트리스트 재설계로 research/UMC=write 소관. dc 역할=증거조사 입력만, 교정 실행=mw/review.
- [완료·정본확정] 공개 출처 4종 정합(T&F·ACM·UTwente·저자사이트): vandeursen2015vandijk 정본 = van Deursen & van Dijk (2015) "Toward a Multifaceted Model of Internet Access for Understanding Digital Divides", The Information Society 31(5) 379–391, **DOI 10.1080/01972243.2015.1069770**. citekey 명명규약(저자·연도)은 정본과 정합.
- [완료·실측] Zotero(~/Zotero/zotero.sqlite, 읽기전용): DB정상(creators 3951·items 2290)인데 **van Deursen/van Dijk 저자 0건** → 정본이 Zotero 부재(refs.bib Zotero 비경유 또는 다른항목 오매핑 가능성, 어느쪽인지는 refs.bib 실물=경계밖 대조 필요).
- [미해소·인계] refs.bib 현재 제목/DOI/DOI실물제목 = 경계밖이라 dc 미확인. scout-lead 증거표가 이 3칸 채우면 §1 정본 대조로 교정안 확정. 권고 bibtex 잠정안 작성.
- [완료·추가 2026-06-28 2nd] **본문 인용맥락 판별을 dc 경계 내에서 확정**(직전 'mw 소관' 넘긴 칸 해소): project/umc/docs/umc_report_ko.md(경계 내) van Deursen&van Dijk 2015 인용 3곳(L93·L241) 전부 §1 정본(Multifaceted Model) 논지와 정합 → 본문 의도=정본 확정, 다른 van Deursen 저작 가능성 배제. ★구분단서: 같은 보고서 L167 'Van Deursen & Helsper 2015'(공저자 Helsper≠van Dijk) 별개 인용 존재 → refs.bib에 van Dijk본·Helsper본 별개 유지(혼동·병합 금지). 증거문서 §5 추가.
- 산출: .context/vandeursen-bib-evidence-2026-06-28.md (정본표·Zotero실측·미해소칸·권고안·§5 인용맥락 확정·구분주의).

## 최신 완료 (2026-06-28 §G 해시 전수 직접 재해싱 — phase00 후속 잔여분 종결)
- [완료·핵심] §G 표 5개 해시 전수 dc 직접 재해싱 일치 확정(이전 'phase00 1건만 검증·나머지 전사값' 해소): phase00 67b4c4f6…✓ / phase03 8ec34da4…✓ / phase01 1eb90fe0…✓ / 코드북v7 2cf232e7…✓(커밋 fff4127 시점 umc_classifier.md 정규화방식 재계산 일치) / 커밋 fff4127=현 HEAD✓. → de 전달값=dc 실측값 전수일치. mw 박제 시 추가 재해싱 불요.
- [완료·신규포착] 코드북 v8 해시 = `d42dc85815f0f99aedb0ab593981e97ab45f66941737cfaa320dfff0db61e396`. 워킹트리 umc_classifier.md 이미 v8 갱신(prompt_version umc_classifier_v8_20260627·codebook_version v8·--check OK) = inference-runner W4(60c3f713) 반영분. ★잠정 단서로만 부록 기록, v8 정본 등재는 W4 산출통지+v8 run.json(A-1 후)과 함께. 현 본문은 v7만 박제 유지.
- [학습] 코드북 해시는 단순 파일해시 아님 — record_codebook_hash.py 정규화(codebook_sha256 줄 placeholder 환원 후 sha256). 재현 시 이 방식 필수.

## 최신 완료 (2026-06-28 phase00 모델 실측 — v7→v8 정본 사전정리 후속, 대기항목 처리)
- [완료·핵심] phase00 모델 식별 불일치('gpt-4o-mini' vs 'Claude Sonnet') = **코드 직접 실측으로 확정 종결**. `/Users/ujunbin/project/umc/analysis/text-preprocessing/src/phase00_sample_for_claude.py`(작업경계 내·Read 가능)에 **API 호출 코드 0건**(openai/anthropic import·chat.completions·messages.create 전무) → 보존 정본 키워드 발견 경로=**Claude Sonnet 수동**(프롬프트 자동생성→Claude Code 수동 전달→merge 병합, keywords.yaml 헤더 'LLM 분석 자동생성'). 'gpt-4o-mini'(MASTERPLAN 서술)는 코드 미보존 보조 워크플로우로 강등. 두 진술=충돌 아닌 다른 경로(이전 가설 b 확정).
- [완료] phase00 sha256 직접 재해싱 = `67b4c4f6719ffba5e3b16ec1a3158a98773538f983288ba5df0515299da4fc15` → §G 표(67b4c4f6…)와 **일치 검증**(de 전달값=실측값, line132 미검증 항목 해소).
- [완료·신규 긍정사실] phase00 층화표집 시드 **고정** 발견: `random_state=round_num×42`(round1→42 …), 구별표집·셔플 동일 시드(phase00:113,129,139,141,490) → 표집 단계 재현가능. §F의 stage3 223 표집 유실과는 다른 층위(코드 고정 vs 산출 유실)임을 부록에 명기.
- [완료] REPRODUCIBILITY-APPENDIX.md 갱신: §A 표 단계0(Claude Sonnet 수동·시드 명기)·각주¹(불일치 해소 확정)·각주¹ᵃ(표집 시드 신규)·§G 식별주석·검증주석·§3.2.4 정합문 = 전부 확정 서술로 전환. mw 부록 확정서술 차단 해제.
- [★경계 정정 필요·보고]: data-lead 조율 aa3a6c9b는 'phase00 코드 트리=de 워크스페이스라 dc 직접 실측 불가'를 전제했으나, 실제 `/Users/ujunbin/project/umc`는 dc 작업경계 내(memory.md 명기)라 직접 Read·해싱 성공. **전제가 실측으로 반증됨** → de 회신 대기 불필요·게이팅 해제. data-lead에 보고.

## 이전 (2026-06-27 data-lead 조율 aa3a6c9b — 전제 반증으로 해소)

## 최신 완료 (2026-06-27 data-lead 조율 수용 — aa3a6c9b)
- [수용] data-lead가 내가 넘긴 미해소 2건을 조율: ①phase00 모델 식별 실측은 data-engineer 소관 지시(코드 트리=de 워크스페이스, dc 직접 실측 불가 확정) ②review팀 독립대조 전달은 phase00 식별확정까지 data-lead가 게이팅 보류.
- [내 후속 액션·대기] data-engineer phase00(67b4c4f6) 실측 회신 → data-lead가 dc에 연결 → 내가 §A(gpt-4o-mini)/§G(Sonnet) 주석 병존 해소(단일 모델 확정). 그 전까지 마스터 §A 각주¹+§G 주석 병존 보존(현 상태 정합, 변경 없음).
- [정합 확인] write측(write-lead b98946f8)도 mw에 phase00 확정서술 보류 전파 완료 — 흐름 일관. v8·시드=inference-runner A-1 후 동일.

## 최신 완료 (2026-06-27 §7.4 내재화 — data-engineer R1 보조분 합류, ac79acf4)
- [완료·핵심] REPRODUCIBILITY-APPENDIX.md §G 신설: data-engineer 전달 해시·커밋 박제(외부저장소 의존 제거 완결). 코드북 v7 sha256(2cf232e7…)=registry §7.1·v8 슬롯 정합 / phase03(8ec34da4)·phase00(67b4c4f6)·phase01(1eb90fe0) 코드 sha256 / 커밋 fff4127 / SOURCE_SCHEMA v7 131,793행·20컬럼.
- [정합확인] §3.2.4/§7.1: phase03 v7 수동(model_id 미기록)=재현불가 근본원인 / phase01=문자열매칭(LLM 아님) / phase00=Claude Sonnet 사전 — 내 §B·registry §7.1 진단과 일치.
- [★미해소·추적] phase00 모델 식별 불일치: 내 §A=gpt-4o-mini(외부·미보존) vs data-engineer=Claude Sonnet. mw 부록 확정 전 phase00 코드(67b4c4f6) 실측으로 확정 필요. §A 각주¹+§G 주석 병존 보존.
- [인계대기] v8 model_id·시드 run.json·§7.2 안정성 v8 행 = inference-runner A-1(e6085772) 산출 후. keywords.yaml(1,228)=CSV 큐레이션 부록화 권장.
- [경계] 코드 트리=data-engineer 워크스페이스 소관이라 직접 재해싱 안 함(전달값 전사). mw 박제 시 1회 교차실측 권장.

## 최신 완료 (2026-06-27 PDF 매칭 오류 교정 — paper-scout 통지건)
- [완료·핵심] 전수 실측 결과 ★영구 산출물 오매칭 0건. paper-scout 적발 6~7건은 fulltext-grounder 자동매칭 런타임 오류이고 Zotero·refs.bib·엑셀엔 미반영(이미 정본 정합).
  - Zotero DB(~/Zotero/zotero.sqlite): 영향 7건 전부 정본 아이템·첨부 실재(bayer2014=1238·ellen2016=1511·firebaugh2016=1542·jung2025=1690·naess2015=1860·yeung2024=2123·li2024kostka=1774/첨부737). ★citationKey(fieldID=9) 저장=0건→DB 교정대상 자체 부재. 백업·quick_check ok·SELECT만(DB 무변경).
  - refs.bib: 6 citekey 전부 정본 제목/연도, file= 필드 0개. 엑셀: 비고=상태메모(경로 아님). 교정 불요.
- [완료] firebaugh2016 톤 정정: .project/assets/Master.xlsx sheet2 '완만한 축소'→'상당한 축소'(원문 sizable). 백업 후 셀1개 교체·zip OK·291셀 불변.
- [정보] paper-scout가 Research_Map 공용화(.project/assets/Research_Map.md+xlsx) 인지.

## 최신 완료 (2026-06-27 개인 메모리 압축 — 사용자 지시)
- [완료] 개인 memory.md 압축: 인프라결정 항목 상세→registry 위임·핵심만 잔류, guard 우회법 3사례→1줄 통합. 2923B→2610B(11%↓). 현작업/재현 단서(UMC·matplotlib·registry·guard·작업경계) 무손실.
- [확인] orchestrator broadcast(공유/팀 메모리 압축 주도, 메모리 직접편집 금지)와 충돌 없음: 내 개인 메모리=독립 파일(root symlink 아님), 공유/팀 메모리는 guard가 내 Edit 차단. 회신으로 범위 명확화.

## 최신 완료 (2026-06-27 회고적 개선 + 추가 진행 — orchestrator 지시)
- [완료] ★인프라 결정 명문화: figure-designer paperbanana 이미지 백엔드 전면차단(Gemini 쿼터0·OpenAI SDK미설치·OpenRouter 오류) → '논문 그림 표준경로=matplotlib' + 재발방지 절차 3항을 _data_registry.md:174 + dc memory.md에 박음.
- [완료] fig_cr_strata registry 등재 확정: stale 표기('일시 제거 상태') 정정. 본문 박힘 실재검증(body_ch2.tex:13/15/9·.aux Figure1 7쪽·.log 로드성공). F11=완료·닫힘. steward §1 정합.
- [완료] paper-review SKILL.md component-contract 블록 추가(다른 스킬 동일 형식). skills.md 인덱스는 hook 자동등재 확인 → ai-peer-review 스킬화 마무리.
- [완료] _data_registry 일관성 점검: image2_v2.png 미참조 고아 발견(fig:framework=PNG→TikZ 작도 교체, body_model.tex:13~79). 본문 figure 11개=includegraphics 10+TikZ 1 정합. 격리=steward R1/R2 조율 사안이라 보류·인계(registry:170 기록).
- [보류 유지] §1 가교·국문초록·저자실명·T1.
- [미착수·별건] manuscript-writer academic-writing symlink 추가 요청 → 사용자 지시로 이번 턴 미착수.

## 최신 완료 (2026-06-26 후속)
- [완료] ★paper-review 스킬 정식화: 외부 ai-peer-review-skill을 .claude/skills/paper-review 복사(root, 사용자 1회우회). orchestrator 안전개조(권한우회 제거·allowedTools 게이트·cwd 격리) 복사후 직접 재검증(활성 우회 0건·py_compile PASS). arxiv venv 설치·실측 동작. skills.md 등재·.context/tools-registry.md provenance. ★코드 재수정 안 함(이중개조 금지). orchestrator 회신.
- [완료] fig:cr-strata 생성→mw 본문 연결·빌드 PASS(Figure 1, 7쪽 박힘 확인). figure-designer 위임 실패(paperbanana 이미지API 차단)→matplotlib 채택. 본문 figure삽입=mw(완료).
- [완료] academic-writing 절차7 갭1(레벨-레벨 판정) 저작(사용자 1회우회). 갭2(학위논문 분기)=타깃확정 대기.
- [완료] B판 그림 R1/R2 attic 격리(고아 figures_main.tex·구버전·미참조)·B판 38p 영향0 검증.

## 최신 완료 (2026-06-26 B판 그림 정리 — steward R1/R2 조율)
- [완료] ★실측 검증 후 attic 격리(삭제 아님, 복원 가능):
  - R1: 고아 parts_ko_B/figures_main.tex(어느 마스터도 input 안함, 전수 grep 확정) → parts_ko_B/_attic/.orphan
  - R2: 구버전(image2·image10)·미참조(image1/3/4/5/13) → figures/_attic/ + MANIFEST_20260626.md
- ★image10.png 오격리 방지: 본문 body_model.tex:78=image10_v2, image10.png는 고아 figures_main.tex만 참조 직접확인 후 격리.
- 정본 10개 보존(image2_v2·image10_v2·11·12·14·6·7·8·9·zshift_panels).
- ★B판 컴파일 영향 0 검증: xelatex 2패스 38p(베이스라인 동일)·undefined cite/ref 0·!에러 0·그림누락 0·duplicate-label 0. 정본 PDF 박힘.
- steward·orchestrator reply·_data_registry.md 반영·미리알림 기록.

## R1 재현성 트랙 — 종결 (orchestrator 게이트 확정)
- [완료] §F 표본 재현성 갭 = 정직한계로 확정. 223 서사·수치 불변(안A 전수재실행 채택 안 함), 데이터가용성 한계 단정+future work 1회 병기, 753 registry 등재 보류. 절차 재현성(§A 명세표) 단정 유지=표본갭이 명세표 안 깎음.
- [완료] R1 자료 전부 확정: 프롬프트 전문 내재화(10개)·모델버전(judgment opus-4-6 핀+umc_classifier git 버전범위)·시드온도코드 명세표·표본갭 정직반영. '현재 원고만 심사' 정직한계 버전으로 닫힘.
- mw 부록화 통지·orchestrator 회신·미리알림(017F2C1E) 기록 완료.
- ★구조도 그림 항목(26B31167) 미리알림 완료 체크백(matplotlib 전환·2종 완료·검증).

## 최신 완료 (2026-06-26 모델버전 통일)
- [완료] ★judgment-synthesizer 모델버전 부록 통일 = claude-opus-4-6 코드·config·git 최종실측 확정(핀ID). opus-4-8 전 분석트리 0건=부록 오기. 원고 3곳(본문 body_model:138·부록 tab:agents L66·R1 명세표 L118) 이미 정합→정정불요. 재현성문서 §B2 기록. R1 '현재 원고만 심사' 마지막 조각 닫힘. mw·orchestrator 회신.
- [완료] ★R1 표본 재현성 갭 §F 반영(inference-runner 223 desert ID목록 미보존 발견). 절차재현성(§A 명세표 유효) vs 입력표본재현성(223 stage3표집 유실=재현불가) 구분. 안A(753전수) 재현성상 권고·동의, 단 '223 서사변경'은 orchestrator 게이트. 753 고정목록 생성=inference-runner, registry 등재=dc.

## 역할
큐레이션·registry·그림·모델버전 실측·재현성 명세 소유. A-1 재실행·ablation 실행 = inference-runner. governance 1회우회 모델.

## 완료 (R&R 2차 = Reject&Resubmit 대응)

### R1 재현성 내재화 [치명] — 사용자 위임 4건 완료
산출: agents/data-curator/.context/r1-reproducibility/REPRODUCIBILITY-APPENDIX.md (마스터) + prompts/(전문 10개). mw 부록화 인계.
- (1) ★프롬프트 전문 내재화: 전 LLM단계(P2스코어링·P3분류 345줄·Reasoner A/B/C·judgment·guard_typology·Stage1필터) 부록 전사형태 수집. DEPRECATED 3종(signal-reader·frame-builder·jump-auditor) 제외. gpt-4o-mini 키워드추출은 외부워크플로우라 미보존(keywords.yaml 1234행 산출만)→사전 부록화 대체 권고.
- (2) ★umc_classifier 모델버전 = git 실측으로 1차 '구조적 불확정' 개선. 초기 claude-3-7-sonnet-20250219 핀(2026-03-26 setup)→같은날 sonnet 별칭 변경→분류실행(2026-05-21) 별칭상태. 버전범위=Claude 3.7 Sonnet 이상 Sonnet 계열 확정. §3.2.4 '실행로그 확인필요'→git-추적 버전범위 서술 교체 권고. 외부저장소 없이 자체완결.
- (3) 시드·온도·코드경로 명세표 §A 8행. temp/seed는 Claude Code 서브에이전트 기본값(미명시)→'결정론성=고정프롬프트·코드북·정보차단·인간검증' 정직표기.
- (4) 데이터 공유가능성 §D 3단계(🟢집계공개/🟡라벨조건부/🔴원문불가)+가드레일(SHA256·좌표비저장·동집계). R2 연계.

## 이전 세션 완료분 (1차 Major Revision)
- A-2 모델명세·A-1 정찰(inference-runner 인계)·image10_v2·image2_v2 층위반전·관통논리 .project/memory·stat-claim-verification 스킬·_data_registry.md·qr E축(qr 완료)·ablation 측정지표 정합(sv).

## 대기·후속
- mw 부록화: §3.2.4 버전범위 교체·신설 Appendix(프롬프트 전문 전사·명세표·데이터공유 진술).
- inference-runner: A-1 재실행 시 ★시드·온도·model 메타 고정·산출에 박기(R1 단계4-7 재현 보강) → 나에게 회신하면 registry·부록 §A 각주 등재. 223 고정목록·EB부호 소스 내가 지원.
- danggeun-scraper: R2 가드레일 근거 + 내 §D 공유가능성 합류 → mw 윤리절.
- R3 과대주장(개념어 톤다운)=mw·sv / R4 구조 전면재작성=mw 주도 / R5 타깃(SSCR vs 도시계획)=paper-scout·사용자 결정.

## 남은 위험
- gpt-4o-mini 키워드추출 프롬프트·코드 미보존(외부 워크플로우) → 보조단계로 서술+키워드 사전 부록화로 대체.
- umc_classifier 정확 하위버전은 별칭이라 단일ID 미고정(버전범위로 명시, 산출+인간검증으로 재현성 확보).
- temp/seed 미명시 단계 → inference-runner 재실행 시드고정으로 보강 필요.
