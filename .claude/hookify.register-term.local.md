---
name: remind-register-term
enabled: true
event: prompt
action: warn
conditions:
  - field: user_prompt
    operator: regex_match
    pattern: (용어|단어|어휘).{0,8}(등록|정의|추가|사전)|word\.json|register[- ]?term|terminolog
---

📖 **용어 등록 — `register-term` 스킬 절차를 따르세요**

사용자가 용어/어휘 등록 의도를 보였습니다. 즉흥적으로 `word.json`을 편집하지 말고 `register-term` 스킬을 사용하세요.

**핵심 원칙**
- 4개 필드(`term`/`ko`/`definition`/`use_when`)가 모두 분명해질 때까지 등록하지 마세요.
- 정의가 모호하거나 누락됐으면 **추측하지 말고 사용자에게 명확히 물어보세요.**

**실행**
```bash
python3 .claude/skills/register-term/scripts/register_term.py add \
  --term "<원어>" --ko "<한국어>" --definition "<정의>" --use-when "<사용 맥락>"
python3 .claude/skills/register-term/scripts/register_term.py --check
```

자세한 절차·기준은 `.claude/skills/register-term/SKILL.md` 참고. 이 메시지는 절차 누락 방지용 리마인더입니다.
