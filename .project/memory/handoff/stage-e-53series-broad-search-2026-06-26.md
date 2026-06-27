# §3.4 53계열(지지전용 단계E 판정) 산출물 — 광범위 재탐색 결과

날짜: 2026-06-26 / 작성: orchestrator
계기: 사용자 "아마 데이터 있을텐데? 일단 보류" — data-curator P0가 한 트리만 봤을 가능성(stats-validator 베타-이항 사례처럼) 점검.

## 결론: row-level 판정 산출물 = 전 트리 부재 재확정 (보류)

Explore 에이전트로 3개 경로 very-thorough 탐색 → data-curator 부재 확정과 독립 일치.

### 탐색 범위 (작업경계 내 전부)
- /Users/ujunbin/project/umc/analysis/03. Test-for-inference/output/  → 단계B 가설·saturation·audit만, 판정 없음
- /Users/ujunbin/project/umc/analysis/part 3/03_inference/output/     → saturation·district_level만
- /Users/ujunbin/research/UMC/active_inference/reproduction/          → JSON은 '학습 결과(learn_result)'일 뿐, 판정 데이터 아님

### 시그니처(찾던 것): CQ40·SAF6·AFF4·DSK3 / medium50·low2·high1 / local46·inst4·indiv3 (합53), 중랑106·강북13·노원7(합126), 772→490/156/126, supported/refuted/undetermined+confidence+dimension+level, desert 3구 223건

### 핵심 발견
1. 53계열·126계열 수치는 본문 tex(parts/body_results.tex, parts/tables_main.tex tab:stage_e)와 figure에만 박제됨 — 산출 데이터 파일 아님.
2. ★설계-구현 불일치: part 3/03_inference/CLAUDE.md는 output/judgments/(C–E 판정)·output/aggregate/(집계)를 명시하나 실제 파일시스템에 그 폴더 없음. → 판정 데이터가 파일로 영속화되지 않음.
3. judgment-synthesizer.md·guard_typology.py 정의는 2개 트리에 존재(03. Test-for-inference, part 3/03_inference). 재실행은 가능하나 입력 가설이 구 가추 구조라 스키마 매핑 필요.

## 처리 결정 (사용자: 보류)
- LLM 재실행 안 함. 53계열은 quality-reviewer R3 봉합대로 '탐색적 윤곽·[불확실]'로 본문 유지(현 §4 PASS 상태).
- 확정 보존: 126·156·490·772, 중랑106·강북13·노원7, 차원합53 값 자체(40/6/4/3 등) — 임의 보정 금지.
- 재개 조건: 사용자가 재현성 완성을 요구하면 → judgment-synthesizer 223건 재실행(스키마 매핑·223건 표본 목록 특정 선행). 결과가 현 수치와 다를 수 있어 본문 수정 연쇄 리스크.

## 잔여
- §4.3 근본해소(EA5132EC)는 '보류' 상태로 닫지 않고 추적 유지. 투고는 [불확실] 표기로 진행 가능.
