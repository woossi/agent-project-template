# 스킬: create-team-agent

## 사용 시점

팀에 **새 동질 peer 에이전트(1계층 폴더)를 생성**할 때. 생성 시점은 **사용자가 판단**하며, 이 스킬은 폴더 스캐폴딩 + 정체성 + 공유 자산 배선 + 로스터 등록을 한 번에 한다. 생성 후 그 에이전트의 모든 자산은 기존 개별 루프로 자동 관리된다(별도 관리 불필요).

서브에이전트(부모 안의 일꾼)가 필요하면 `write-subagent`를 쓴다. 이 스킬은 **독립 peer**(자기 컨텍스트로 터미널에서 실행되는 에이전트)를 만든다.

## 목적

Model Y 구조로 `agents/<name>/`를 만든다 — **개별(사적)** 자산은 실파일, **공유(단일소스)** 자산은 root `.claude`로 symlink. 동질성이 구조적으로 보장되고(공유는 1벌), 정체성만 다르다. `agent-clone-setup`의 템플릿 전환 아이디어를 참조하되 **역할별 계약 rewrite는 하지 않는다**(peer는 구조가 동일해야 함).

## 계약

- 읽는 입력: 에이전트 이름, 선택적 role 설명, team root(기본 = repo root). 공유할 root `.claude` 서브트리.
- 만드는 출력: `agents/<name>/`(아래 레이아웃), `.team/team.json` members 등록.
- 쓰면 안 되는 위치: 공유 계약(`AGENTS.md`/`.claude/CLAUDE.md`)을 역할별로 rewrite하지 않는다(동질성 파괴). 기존 에이전트의 사적 자산을 덮지 않는다(`--force`도 seed는 보존).

## 입력

- 고유한 에이전트 이름(폴더·정체성·로스터 키로 쓰임).
- (선택) `--role` 한 줄 설명 — 공유 계약을 바꾸지 않고 `AGENT.md` 디스크립터에만 기록.

## 절차

1. **생성:**
   ```bash
   python scripts/team_agent.py create <name> [--role "<설명>"]
   ```
   기존 폴더를 다시 배선하려면 `--force`(사적 seed는 보존, 끊긴 symlink만 복구).
2. **정체성 주입(런치 계약):** 그 에이전트로 일할 터미널에서 `export CLAUDE_AGENT_NAME=<name>` 후 `agents/<name>/`에서 `claude` 실행. 이 값이 guard·받은 편지함·팀 신호의 정체성이다.
3. **스킬 동기화(공유 스킬 추가/삭제 후):**
   ```bash
   python scripts/team_agent.py sync --all          # 전 에이전트 재배선(없는 공유 스킬 symlink 추가, 사라진 것 prune)
   python scripts/team_agent.py sync <name>          # 한 에이전트만
   ```
   전용 스킬(실디렉토리)은 절대 건드리지 않는다. 기존에 `skills`가 통째 symlink였던 에이전트는 `sync --force`가 실디렉토리로 마이그레이션한다.
4. **확인:** `python scripts/team_agent.py list`로 폴더↔로스터 정합(`out_of_sync` 비어야 함)을 본다.

생성되는 레이아웃:
```
agents/<name>/
  .claude/
    memory/  (사적)  memory.md · user_preferences.md · word.json
    tasks/   (사적)  tasks.md
    hooks/ policies/ settings.json CLAUDE.md  → root .claude로 symlink (공유, 통째)
    skills/  (실디렉토리)  공유 스킬은 개별 symlink, 전용 스킬은 실디렉토리로 공존
      <공유>  → ../../../../.claude/skills/<공유>   (공유 스킬마다 1개)
      <전용>/ (사적)  이 에이전트만의 전용 스킬
  AGENTS.md  → 루트로 symlink (공유)
  AGENT.md   (role 디스크립터)
  .context/  (사적, gitignore)
```

`skills`만 통째 symlink가 아니라 **실디렉토리 + per-skill 배선**이다(`_wire_skills`). 통째 symlink면 전용 스킬을 넣는 순간 root 공유로 새어 모든 peer에 노출되기 때문이다. 실디렉토리 안에서 공유는 symlink, 전용은 실디렉토리로 공존해 단일소스와 격리를 동시에 만족한다.

## 출력 형식

```json
{ "ok": true, "op": "create", "result": {
  "name": "worker-2", "dir": "agents/worker-2", "created": true,
  "symlinks": {"hooks": "created", "policies": "created", "settings.json": "created",
               "CLAUDE.md": "created", "skills": "wired", "skills/team-inbox": "created",
               "AGENTS.md": "created"},
  "roster_added": true } }
```

`sync`의 출력은 `result.skills`(또는 `sync --all`이면 `result.skills.<name>`)에 `{ "wired": <_wire_skills 결과>, "pruned": [...] }` 형식으로 담긴다. `_wire_skills`는 공유 스킬을 `skills/<name>: created|ok`로, 전용 스킬은 `private (kept)`로 보고하고, `pruned`는 공유 소스가 사라져 제거된 stale symlink다.

## 내부 자원

- `scripts/team_agent.py` — CLI/라이브러리. `create`(스캐폴딩+정체성 규약+공유 symlink+per-skill 스킬 배선(`_wire_skills`)+로스터 등록, 멱등, `--force`로 재배선하되 seed 보존), `sync`(스킬 폴더를 공유 단일소스에 맞춰 재배선 — `_wire_skills` 재사용으로 공유 추가·전용 보존하고 stale symlink prune, `--all`/한 에이전트, `--force`로 통째 symlink 마이그레이션), `list`(폴더↔로스터 drift). 로스터는 `.team/team.json` members를 원자적(`os.replace`)으로 갱신.
- `scripts/tests/test_team_agent.py` — CI 안전 단위 테스트(임시 team root): 구조·시드·symlink 타겟·로스터·멱등·`--force` seed 보존·drift 보고·CLI 왕복, per-skill 배선·전용 보존·통째 symlink 마이그레이션·`sync` 재배선·stale prune·`sync --all`.

## 품질 점검

- `python3 -m pytest .claude/skills/create-team-agent/scripts/tests/ -q` 통과.
- 공유 symlink는 root `.claude/{hooks,policies,skills,settings.json,CLAUDE.md}`로 해석되어야 한다.
- `--force` 재실행이 사적 memory/tasks seed를 덮지 않아야 한다.
- 런치 후: `agents/<name>/`에서 `CLAUDE_PROJECT_DIR`가 그 폴더로 앵커되어 hook이 `agents/<name>/.context/`에 기록(개별 격리)되어야 한다.

## 자주 발생하는 실패 사례

- **`team root has no .claude/`** → repo root가 아닌 곳에서 실행. `--team-root`로 지정하거나 root에서 실행.
- **기존 에이전트에 `create`가 "exists"만 반환** → 의도된 멱등. 재배선이 필요하면 `--force`.
- **공유 skill 파일을 Read 툴로 직접 열다 guard 차단** → 정상(symlink가 root 밖으로 풀림). 공유 skill은 Skill 툴/autoload로 참조하고, 사용 기록은 팀 recorder가 stamp(팀 계층 계획 §3.6).
- **정체성 미설정으로 `main` 붕괴** → 런치 전 `export CLAUDE_AGENT_NAME=<name>` 필수.

<!-- component-contract:start -->
## 계약 연계

- 스킬은 반복되는 작업 묶음을 하나의 포괄 이름으로 승격한 재사용 절차다.
- 작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다. 절차를 복사하지 않는다.
- 서브에이전트는 작업 입력을 받아 필요한 스킬 능력을 사용한다.
- 현재 진행상황과 handoff는 스킬에 저장하지 않는다.
<!-- component-contract:end -->
