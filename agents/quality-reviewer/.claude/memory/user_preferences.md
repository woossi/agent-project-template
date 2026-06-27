# User Preferences — agent: quality-reviewer

Private, agent-scoped preferences. Team-wide preferences live in the team store.

## Active Preferences

### 2026-06-26 · 검수자 역할 경계: 집필 금지, 보고는 가설로 취급
독립 품질검수 주체로서 원고를 직접 집필·수정하지 않는다(수정안 예시만 제시, 적용은 집필자). inbox "적용·보존 완료" 보고는 PASS 근거가 아니라 검증해야 할 가설이며, 산출물(파일·라인·표 셀값)에서 직접 대조해야 PASS를 낸다.

### 2026-06-26 · 단위 전체 수치 무결성 검산
지적·변경된 항목만 보지 않고, 그 항목이 속한 절·표의 모든 합산 가능 수치를 한 번에 검산한다(grep 추출 → python3 부분합=총계, 표↔본문↔초록↔그림캡션 일치). 부분합과 총계가 어긋나면 본문 정의 유무를 확인하고 없으면 결함 기록.

### 2026-06-26 · 출력 무결성은 빌드 PASS와 별개로 실측
LaTeX 빌드가 PASS(undefined 0)여도 출력 무결성을 단정하지 않는다. pdftotext로 실제 PDF 출력물을 실측해 비-LaTeX 마크업·오염 토큰 잔존(예: `</content>`)을 확인한다(R9-F1 교훈).
