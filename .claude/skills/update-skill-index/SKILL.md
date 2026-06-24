# 스킬: update-skill-index

## 사용 시점

새 스킬 폴더를 추가·삭제·이름변경했거나, `skills/skills.md`의 영어 **Skill Index** 표를 최신 상태로 맞춰야 할 때.

## 목적

`skills/`를 스캔해 영어 **Skill Index** 표를 자동으로 재생성한다. 한국어 `SKILL.md` 본문을 색인에 복사하지 않고, 영어 kebab-case 폴더명을 라우팅 신호로 사용해 색인을 영어로 유지한다.

## 입력

- `skills/` 디렉터리 (각 스킬 폴더에 `SKILL.md` 존재)
- 별도 인자 없음. 필요 시 `--skills-dir <경로>`로 대상 지정.

## 절차

1. `.claude/settings.json`의 `ConfigChange` 훅이 `skills` 변경을 감지하도록 켜져 있는지 확인한다.
2. 스킬 폴더의 `SKILL.md`가 추가·수정되어 Claude Code가 skills 구성 변경을 감지하면, 훅이 내부 스크립트를 실행해 영어 색인을 자동 갱신한다.
3. CI나 커밋 전 점검에서는 점검 모드로 색인이 최신인지만 검사한다(변경 필요 시 종료코드 1).
4. `skills.md`의 **Skill Index** 표가 현재 스킬 폴더 목록과 일치하는지 확인한다.

## 출력 형식

`skills/skills.md`의 `## Skill Index` 섹션(헤더~다음 `---` 또는 `## ` 직전)만 다음 영어 표로 재생성된다. 색인 아래의 다른 본문은 보존된다.

```md
## Skill Index

| Skill | Folder | Load rule |
| --- | --- | --- |
| update-skill-index | `update-skill-index/` | Open `update-skill-index/SKILL.md` only when the request clearly matches the `update-skill-index` workflow. |
```

## 내부 자원

- `scripts/update_index.py` — `skills/`를 스캔해 `skills.md`의 영어 Skill Index 표를 재생성하는 실행 코드. `--check`(점검 전용), `--skills-dir`(대상 경로) 옵션 지원. 훅에서 호출되며 일반 사용자가 직접 실행하지 않는다.

## 품질 점검

- 점검 모드가 종료코드 0이어야 한다(= 색인이 최신).
- `_`로 시작하는 폴더(예: `_template/`)는 색인에 포함되지 않아야 한다.
- 각 행의 폴더 경로가 실제 존재하는 스킬 폴더와 일치해야 한다.
- 생성된 표의 헤더와 설명 문구는 영어여야 한다.

## 자주 발생하는 실패 사례

- `SKILL.md`에 `# 스킬: <이름>` 제목이 없으면 → 폴더 이름을 스킬 이름으로 대체한다. 제목 줄을 채워 해결.
- 스킬 폴더명이 한국어이거나 공백을 포함하면 → 영어 색인의 라우팅 신호가 약해진다. 영어 kebab-case 폴더명으로 바꾼다.
- 훅 환경에서 `skills.md`를 못 찾는다 → `CLAUDE_PROJECT_DIR`와 `.claude/settings.json`의 `ConfigChange` 훅 경로를 확인한다.
