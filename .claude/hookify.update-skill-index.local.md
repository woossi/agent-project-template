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

📑 **스킬 색인 갱신 필요**

방금 스킬 폴더의 `SKILL.md`를 추가/수정했습니다. `skills/skills.md`의 **스킬 색인** 표가 더 이상 최신이 아닐 수 있습니다.

**해야 할 일** — 저장소 루트에서 색인을 재생성하세요:

```bash
python3 .claude/skills/update-skill-index/scripts/update_index.py
```

**확인** — 갱신이 끝나면 색인이 최신인지 점검하세요 (종료코드 0이어야 함):

```bash
python3 .claude/skills/update-skill-index/scripts/update_index.py --check
```

**참고**
- `# 스킬: <이름>` 제목과 `## 목적` 절이 채워져 있어야 색인의 이름·설명이 올바르게 추출됩니다.
- `_`로 시작하는 폴더(예: `_template/`)는 색인 대상이 아니므로 갱신이 필요 없습니다.
- `settings.json`의 `FileChanged` 훅이 정상 동작하면 이 갱신은 자동으로 실행됩니다. 이 메시지는 누락 대비 리마인더입니다.
