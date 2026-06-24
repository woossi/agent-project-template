# Agent Policies

Machine-readable policy files consumed by the project hooks. Two policies ship today:

- `agent-workspace.json` — workspace and Bash boundaries for `.claude/hooks/guard_agent_workspace.py`.
- `promotion.json` — concrete skill/agent promotion conditions for `.claude/hooks/detect_promotions.py`.

## Agent Workspace Policy

`agent-workspace.json` is the machine-readable policy used by `.claude/hooks/guard_agent_workspace.py`.

## Shape

```json
{
  "version": 1,
  "defaults": {
    "allow": ["."],
    "deny": [],
    "bash": {
      "allow": [],
      "deny": []
    }
  },
  "agents": {
    "agent-name": {
      "allow": ["src/**"],
      "deny": ["src/generated/**"],
      "bash": {
        "allow": ["rg *", "sed *"],
        "deny": []
      }
    }
  }
}
```

`allow` and `deny` are project-relative path globs. Agent entries override `defaults.allow`, extend `defaults.deny`, and can narrow Bash command usage with `bash.allow`.

## Default: allow every tool inside the workspace

The shipped defaults grant every tool inside the project root, and that is the
intended baseline — keep it permissive so ordinary commands are not blocked.

- `allow: ["."]` lets path tools (Read/Edit/Write/MultiEdit) touch anything under
  the project root. `"."`, `"**"`, and `"**/*"` all mean "everywhere".
- `bash.allow: []` (empty) means **every Bash command is allowed**; the guard only
  enforces `bash.deny`. The moment `bash.allow` is non-empty it becomes a
  whitelist, so unlisted commands (`ls`, `cat`, `find`, …) get blocked. Leave it
  empty to allow all commands.
- Tools other than path tools and Bash are never blocked by this guard.

Restrict a specific agent only by adding an entry under `agents` (narrow `allow`,
extend `deny`, or set a `bash.allow` whitelist). Do not narrow `defaults`, or the
whole project loses access to normal tools.

## Promotion Policy

`promotion.json` holds the concrete conditions that turn the Tasks → Skills → Agents
chain into an enforced loop. `task_ledger.py` writes the ledger; `detect_promotions.py`
reads this policy, evaluates the ledger, and re-surfaces qualifying candidates.

```json
{
  "version": 1,
  "log": {
    "events": ".context/task-log/events.jsonl",
    "tasks": ".context/task-log/tasks.jsonl",
    "candidates": ".context/promotions/candidates.json",
    "decisions": ".context/promotions/decisions.json"
  },
  "skill_promotion": {
    "min_recurrence": 3,
    "min_distinct_sessions": 2,
    "skip_if_skill_exists": true,
    "max_candidates": 20
  },
  "agent_promotion": {
    "min_package_size": 2,
    "min_cousage": 3,
    "min_distinct_sessions": 2,
    "skip_if_agent_exists": true,
    "max_candidates": 20
  }
}
```

- **Skill condition** — a recorded task `signature` recurs at least `min_recurrence`
  times across at least `min_distinct_sessions` distinct sessions and is not already a
  skill folder. Signatures come from `task_ledger.py record-task`.
- **Agent condition** — a package of at least `min_package_size` skills is co-used at
  least `min_cousage` times across at least `min_distinct_sessions` sessions and is not
  already covered by an agent file. Co-usage is detected deterministically from
  `SKILL.md` reads and recorded task `skills` lists; only the maximal package is reported.
- `skip_if_skill_exists` / `skip_if_agent_exists` suppress candidates that already exist.
- `max_candidates` caps how many of each kind are surfaced at once.

Tune thresholds here, never in the hook code. All log paths stay under `.context/`
(transient, git-ignored). Close a surfaced candidate with
`detect_promotions.py resolve --kind {skill,agent} --key <key> --decision {promote,decline}`.
