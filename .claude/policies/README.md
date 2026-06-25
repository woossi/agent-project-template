# Agent Policies

Machine-readable policy files consumed by the project hooks. Four policies ship today:

- `agent-workspace.json` — workspace and Bash boundaries for `.claude/hooks/guard_agent_workspace.py`.
- `promotion.json` — concrete skill/agent promotion conditions for `.claude/hooks/detect_promotions.py`.
- `derivation.json` — concrete memory→preference/term derivation conditions for `.claude/hooks/detect_derivations.py`.
- `feedback.json` — inter-agent feedback routing and thresholds for `.claude/hooks/detect_feedback.py` (see `FEEDBACK.md`).

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
    "min_recurrence": 1,
    "min_distinct_sessions": 1,
    "skip_if_skill_exists": true,
    "max_candidates": 20
  },
  "agent_promotion": {
    "min_package_size": 2,
    "min_cousage": 1,
    "min_distinct_sessions": 1,
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

The shipped defaults set every count gate to `1` (`min_recurrence`, `min_cousage`,
and `min_distinct_sessions`), so a candidate surfaces on its first occurrence in a
single session — about 3x more frequently than the original `3`/`2` gates, which
required three occurrences spread over two sessions. `min_package_size` is a
structural size gate, not a frequency knob, so it stays at `2`. Raise these values
to make promotion stricter again.

Tune thresholds here, never in the hook code. All log paths stay under `.context/`
(transient, git-ignored). Close a surfaced candidate with
`detect_promotions.py resolve --kind {skill,agent} --key <key> --decision {promote,decline}`.

## Derivation Policy

`derivation.json` is the memory side of the same enforced-loop idea: it holds the
conditions that move a broad durable fact in `.claude/memory/memory.md` into a
narrower store — a stable preference in `.claude/memory/user_preferences.md` or a
term in `.claude/memory/word.json`. `detect_derivations.py` reads this policy,
evaluates the signals, and re-surfaces qualifying candidates until each is derived
and resolved (or declined).

```json
{
  "version": 1,
  "log": {
    "signals": ".context/memory-log/signals.jsonl",
    "candidates": ".context/memory-promotions/candidates.json",
    "decisions": ".context/memory-promotions/decisions.json"
  },
  "preference_derivation": {
    "min_recurrence": 2,
    "min_distinct_sessions": 1,
    "skip_if_recorded": true,
    "max_candidates": 20
  },
  "term_derivation": {
    "min_recurrence": 2,
    "min_distinct_sessions": 1,
    "skip_if_registered": true,
    "max_candidates": 20
  }
}
```

Two deterministic signal sources feed detection:

- **Explicit memory markers** — a `memory.md` entry may carry an optional
  `Derive: preference` or `Derive: term: <word>` line. Such an entry is treated as
  an explicit, already-qualifying signal and surfaces immediately, regardless of
  the recurrence gate. This is the literal "memory → derive" bridge.
- **Recorded observations** — `detect_derivations.py record-signal --kind
  {preference,term} --key <key> --session <id>` appends a semantic observation to
  `signals.jsonl`. A key that recurs at least `min_recurrence` times across at
  least `min_distinct_sessions` sessions qualifies on the threshold, mirroring how
  task signatures drive skill promotion.

- `skip_if_recorded` suppresses a preference key already present in
  `user_preferences.md`; `skip_if_registered` suppresses a term already in
  `word.json` (case-insensitive). `max_candidates` caps each kind.
- Authoring stays a judgment step: a preference candidate is written into
  `user_preferences.md` (confirm it is stable and project-scoped first), a term
  candidate is registered with the `register-term` skill (confirm the four fields
  with the user; never invent a definition). Close a candidate with
  `detect_derivations.py resolve --kind {preference,term} --key <key> --decision {promote,decline}`.
