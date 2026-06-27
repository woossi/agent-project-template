# 스킬: build-verify-latex

## 사용 시점

원고 LaTeX(`umc_paper.tex` 등 xelatex+bibtex 마스터)를 **변경한 뒤 빌드가 깨지지 않고 인용·참조가 수렴했는지 검증**해야 할 때. 구체적으로:

- 섹션 재작성·P0 수정·신규 참고문헌 통합·영문화 등 원고 본문/`.bib`를 바꾼 직후 일괄 검증.
- 투고 패키지·PDF 산출 전 최종 무결성 게이트.

단순히 PDF를 만드는 것이 목적이 아니라, **`latexmk` 단일 호출이 패스를 덜 돌려 `undefined citation/reference` 경고를 남기는 함정**을 제거하고 "정말 수렴했는가"를 결정적으로 판정하는 것이 목적이다. (이 함정은 P0검증·섹션재작성검증·PDF빌드에서 반복 관측되었다.)

## 목적

명시적 다중 패스(`xelatex → bibtex → xelatex×3`)로 cross-reference를 강제 수렴시키고, 빌드 무결성을 단일 게이트(PASS/FAIL)로 판정한다. 사람이 매번 패스 수를 헤아리거나 경고의 진위를 추측하지 않게 한다.

## 계약

- 읽는 입력: 마스터 `.tex` 절대경로 1개(예: `/Users/ujunbin/research/UMC/umc_paper.tex`). 마스터가 `\input`/`\include`하는 파트도 자동 점검.
- 만드는 출력: 빌드 디렉토리에 `.pdf`·`.aux`·`.bbl` 등 표준 산출물. stdout에 게이트 표 + 마지막 줄 `RESULT=PASS|FAIL`. 종료코드 0(PASS)/1(FAIL).
- 쓰면 안 되는 위치: 본문 `.tex`/`.bib`를 수정하지 않는다(검증만, 집필은 academic-writing/직접 Edit 소관). 로그는 임시 디렉토리에 두고 종료 시 정리한다.

## 입력

- `xelatex`, `bibtex` (필수). `pdfinfo`, `pdftotext`(선택 — 있으면 페이지 수·본문 미해소 마커 `??` 점검 추가).
- 마스터 `.tex` 경로 1개. 작업 경계(`/Users/ujunbin/research/UMC`) 안.

## 절차

1. **실행:** `bash .claude/skills/build-verify-latex/scripts/verify_build.sh <master.tex>`
2. 스크립트가 자동으로: (1) 마스터+파트의 환경 균형(`$` 짝수, `figure`/`align` begin=end) 사전점검 → (2) `latexmk -C`로 캐시 제거 후 `xelatex → bibtex → xelatex×3` 명시 다중 패스 → (3) 최종 패스 로그·bibtex 로그·PDF로 게이트 판정.
3. **판정 읽기:** 마지막 줄 `RESULT=PASS`면 통과. `FAIL`이면 게이트 표에서 0이 아닌 항목을 보고 원인(미정의 키·환경 불균형·컴파일 에러)을 좁힌다.
4. FAIL이면 원인을 고치고(키 추가/환경 닫기 등) 재실행. 검증 스크립트는 멱등적이라 반복 실행해도 안전하다.

## 출력 형식

```
== 3) 게이트 ==
  undefined citation : 0
  undefined reference: 0
  rerun 권고         : 0
  Error/Fatal        : 0
  bibtex error       : 0
  PDF 미해소 마커(??) : 0
  PDF 페이지          : 24
RESULT=PASS
```

PASS 조건: 위 수치 게이트가 모두 0 + 환경 균형 OK + `.pdf` 생성됨. 하나라도 위배 시 FAIL(종료코드 1).

## 내부 자원

- `scripts/verify_build.sh` — 검증 CLI. 인자=마스터 `.tex`. 환경 균형 사전점검 → 명시 다중 패스 → 게이트 판정. `set -euo pipefail` 하에서 `grep` 비매치(exit 1)를 `|| true`와 `num()` 보정으로 흡수해 결정적으로 동작. 종료코드로 PASS/FAIL 신호.

## 품질 점검

- 작업 경계 내 실제 마스터(`umc_paper.tex`)에 대해 실행 시 `RESULT=PASS`·종료코드 0.
- 동일 입력 반복 실행 시 동일 결과(멱등). 본문 `.tex`/`.bib` 미변경.
- `latexmk` 단일 호출에서 보이던 undefined 경고가 이 스크립트 후 0으로 수렴.

## 자주 발생하는 실패 사례

- **`RESULT=FAIL`, undefined citation>0** → `.bib`에 키 누락 또는 `\citep` 오타. 키를 `refs.bib`에 추가하거나 인용 키를 교정 후 재실행.
- **`RESULT=FAIL`, 환경 BALANCE-FAIL** → 어느 파트에서 `$` 홀수이거나 `figure`/`align`이 안 닫힘. 표시된 파일을 열어 닫는다.
- **`undefined`가 latexmk로는 남는데 이 스크립트로는 0** → 정상. latexmk 패스 부족 함정이며, 이 스크립트의 명시 다중 패스가 해소한 것이다. latexmk 단일 호출 결과를 신뢰하지 말 것.
- **`PDF 미해소 마커(??)`가 skip** → `pdftotext` 미설치. 선택 점검이라 PASS/FAIL에 영향 없으나, 설치하면 본문 깨진 참조까지 잡는다.
- **본문 `.tex`를 이 스킬로 고치려 함** → 범위 밖. 집필·수정은 별도(academic-writing/Edit), 이 스킬은 검증 전용.

<!-- component-contract:start -->
## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.
<!-- component-contract:end -->
