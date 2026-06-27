# 작업

## 상태
완료

## 목표
ms 요청: B판 2장(body_ch2.tex) 인용 31건의 원문근거를 검증해 CSV 뒤 3열(원문근거_PDF확보·근거페이지/인용구·비고)을 채운다 + 핵심어휘 3개(준규칙성·생활세계 흔적·지역역량) 정의 출처 확인.

## 입력
- CSV: /Users/ujunbin/research/UMC/.context/ch2-citations-for-ps.csv (31행, 앞 7열 채워짐)
- 배치 입력: .context/agents/fulltext-grounder/ch2-batch{A,B,C}.json
- 로컬 PDF: /Users/ujunbin/article/ — ★커버리지 매우 낮음, 매칭된 것 대부분 오매칭(제목 검증 필수) → 주 경로는 OA/scrapling 외부 확보(27건 DOI 보유).

## ★검증 규칙
- 각 인용이 CSV '2장_인용맥락' 주장을 실제 뒷받침하는지 원문 verbatim 대조. PDF확보/근거페이지/인용구 채움.
- 로컬 PDF는 제목·DOI 1차 대조로 동일논문 확정 후만 사용(오매칭 차단). 없으면 OA(Crossref link)→scrapling.
- 못 구하면 비고 '원문 미확보' 정직표기(창작·추정 금지).
- DOI 없는 4건(bhaskar1975·sen1985·raudenbush2002 단행본, itu2025 기관보고서)=서지 2차확인만.
- ms 강조 핵심: bhaskar1975·danermark2019·eastwood2014/2019·perkins1987·gill2005·vangrootel2017 우선.

## 사용할 스킬·서브에이전트
- fulltext-grounder(3배치 병렬, 이번 세션은 general-purpose로 대행), fetch-paper-fulltext, scholarly-evidence-search.

## 산출물
- .context/agents/fulltext-grounder/ch2-grounding-batch{A,B,C}.md (배치별 핸드오프 표)
- 종합 후 CSV 갱신 또는 .context/handoff/로 회신. 핵심어 3개 정의 출처 별도 정리.

## 완료 기준
- 31건 전부 PDF확보 여부·근거페이지/인용구·비고 채워짐. 미확보 정직표기.
- 핵심어 3개 (표준정의 1문장·출처 file:page·본연구 용법 관계) 회신.

## 남은 위험
- 로컬 커버리지 낮아 외부 확보 의존 → 페이월·OA 실패 가능(scrapling 폴백, 그래도 안되면 사용자 Scopus 폴백 후보).
- CSV 갱신·본문 삽입은 검증 후 단계. 본문 인용삽입은 mw 소관.
