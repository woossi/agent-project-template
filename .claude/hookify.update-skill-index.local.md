---
name: remind-update-skill-index
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.claude/skills/[^/_][^/]*/SKILL\.md$
---

📑 **영어 스킬 색인 자동 갱신 확인**

방금 스킬 폴더의 `SKILL.md`를 추가/수정했습니다. `.claude/settings.json`의 `FileChanged` 훅이 `skills/skills.md`의 **Skill Index** 표를 영어로 자동 갱신해야 합니다.

**확인** — `skills.md`의 **Skill Index** 표가 현재 스킬 폴더 목록과 맞는지 확인하세요.

**참고**
- 스킬 폴더 이름은 영어 kebab-case를 쓰세요. 색인은 이 폴더명을 영어 라우팅 신호로 사용합니다.
- `_`로 시작하는 폴더(예: `_template/`)는 색인 대상이 아니므로 갱신이 필요 없습니다.
- `settings.json`의 `FileChanged` 훅이 정상 동작하면 갱신은 자동으로 실행됩니다. 이 메시지는 누락 대비 리마인더입니다.
