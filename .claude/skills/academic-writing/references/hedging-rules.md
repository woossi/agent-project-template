# hedging·불확실성 표기 + AI 티 제거(휴머나이즈)

두 가지를 통합한다: (1) 검증/미검증 주장을 정직하게 구분하는 hedging, (2) AI 생성 티를 제거해 사람이 쓴 학술 산문으로 만드는 휴머나이즈. 둘은 다른 목적이다 — hedging은 *불확실성을 정직하게 표시*, 휴머나이즈는 *문체의 AI 통계 편향 제거*.

> 근거: blader/humanizer(Wikipedia "Signs of AI writing"), Limdongcheng/cc-academic-writing 5대 핵심 금령. **중요 경고(blader)**: AI는 *특정* 화려한 단어를 남용할 뿐, 모든 격식어가 AI 티는 아니다. 정당한 학술 어휘("ostensibly", "constituent")를 납작하게 만들지 말 것.

---

## A. hedging — 불확실성의 정직한 표시

### 확정 vs 잠정 구분
- **검증된 사실**(보존 수치, stats-validator 검증분, [VERIFIED] 인용): 단정한다. 과잉 hedge 금지.
- **미검증·추정**: 명시적 hedge — "suggests", "may", "appears to", "잠정적으로", "불확실".
- **한계**: 논의 섹션에 명시한다.

### 과잉 hedging도 결함
한 문장에 hedge를 쌓지 않는다.
- ❌ "could potentially possibly be argued that the policy might have some effect"
- ✅ "The policy may affect outcomes."

원칙: 검증된 것은 단정, 미검증은 한 번만 명확히 hedge. 모호함을 두께로 늘리지 않는다.

---

## B. cc-academic 5대 핵심 금령 (학술 산문 필수)

1. **Unicode 상하첨자 금지** — ❌ H₂O, CO₂, Fe³⁺ → ✅ `H_2O`, `CO_2`, `Fe^3+`. (편집기 간 복사 시 깨짐. LaTeX이면 수식 모드.) z_shift 같은 변수명도 일관 표기.
2. **Em dash(—)·en dash(–) 금지** — 가장 강한 AI 티. 쉼표·괄호·콜론·마침표로 대체. 최종본에 `—`/`–`가 하나라도 있으면 미완성.
3. **AI 口癖 금지** — ❌ "It is worth noting", "Moreover", "Furthermore", "In order to", "plays a crucial role", "delve", "underscore", "intricate", "pivotal", "tapestry", "landscape(추상)", "testament" → 사실을 직접 진술하거나 구체 동사(governs, determines, controls).
4. **句長 단조 금지** — 연속 5문장이 같은 길이면 AI 티. 짧은 문장(강조)·중간(주체)·긴 문장(복잡 논증)을 섞는다. 句長 분산을 키운다.
5. **미검증 인용 금지** — `citation-evidence.md` 참조. [VERIFIED]/[FROM-BIB]만 단정.

---

## C. blader/humanizer 핵심 패턴 (학술 맥락 적용)

학술 산문에서도 결함인 패턴. (전체 33개 중 학술에 빈발하는 것.)

- **의의 과장(significance inflation)**: "marking a pivotal moment", "represents a paradigm shift", "a vital role" → 한 일을 그대로 기술.
- **-ing 피상 분석**: "highlighting…", "underscoring…", "reflecting…", "contributing to…"를 문장 끝에 매달아 가짜 깊이 부여 → 별도 절로 풀거나 삭제.
- **copula 회피**: "serves as / stands as / represents a" → 그냥 "is/are"를 쓴다.
- **부정 병렬(negative parallelism)**: "Not only… but…", "It's not just X, it's Y" 남용 → 직접 진술.
- **rule of three**: 모든 것을 3개조로 묶어 포괄성 위장 → 실제 항목 수대로.
- **elegant variation(동의어 순환)**: 같은 대상을 매번 다른 말로(protagonist→main character→central figure) → 일관 용어.
- **false range**: "from X to Y"인데 X·Y가 같은 척도가 아님 → 실제 항목 나열.
- **boldface/제목 title case/이모지 남용** → 평문, 문장형 제목, 이모지 제거.
- **persuasive authority("The real question is", "at its core", "fundamentally")** → 평이한 진술.
- **신호어(signposting: "Let's dive in", "Here's what you need to know")** → 바로 본론.
- **일반 긍정 결론("The future looks bright", "exciting times ahead")** → 구체 사실.
- **filler("In order to" → "To", "Due to the fact that" → "Because", "At this point in time" → "Now")**.

---

## D. 과편집 금지 (오탐 방지) — 매우 중요

clean한 사람도 위 패턴 일부를 친다. 정당한 학술 산문을 훼손하지 않는다. 다음은 **단독으로는 AI 신호가 아니다**:

- 완벽한 문법·일관된 문체 (전문가·교정의 결과).
- 격식어·학술 어휘 자체 (AI는 *특정* 단어만 남용. "ostensibly", "constituent"를 납작하게 만들지 말 것).
- 단독 em dash, 단독 curly quote, 고립된 전환어 하나("however" 한 번).
- 단독 짧은 강조 문장.
- 출처 없는 주장 자체 (대부분의 글이 그렇다).

원칙: **고립된 패턴이 아니라 군집(cluster)**을 본다. em dash 하나는 무의미하지만, em dash + rule of three + "vibrant tapestry" + "Conclusion" 섹션이 함께 오면 confession이다.

보존할 인간 글쓰기 신호(건드리지 말 것):
- 구체적·재현 불가능한 디테일(실제 수치, 특이 사례).
- 혼재된 감정·미해결 긴장.
- 변동하는 문장 길이.
- 진짜 여담·자기 수정.

---

## 점검 체크리스트

- [ ] 검증분은 단정, 미검증분만 hedge(과잉 hedge 없음).
- [ ] Unicode 상하첨자·em/en dash가 최종본에 0건.
- [ ] AI 口癖(worth noting/moreover/delve/pivotal 등) 군집이 없는가.
- [ ] 句長 분산이 충분한가(연속 동일 길이 없음).
- [ ] 의의 과장·-ing 피상분석·copula 회피·rule of three 군집이 없는가.
- [ ] **과편집으로 정당한 학술 어휘·디테일을 훼손하지 않았는가.**
