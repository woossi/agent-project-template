# AGENTS.md

## Purpose

This folder is a reusable agent-project template. It fixes the roles and I/O rules for the components that future projects share:

- `AGENTS.md`, `.claude/CLAUDE.md`, `.claude/memory/`, `.claude/skills/`, `.claude/tasks/`
- `.claude/settings.json`, `.claude/hooks/`, `.claude/agents/`, `.claude/policies/`

Keep it project-neutral. Do not customize it to one topic, dataset, method, client, or publication target unless the user explicitly asks for a project-specific fork.

## Authority Order

When instructions conflict, follow this order:

1. Current user request
2. Higher-level workspace or tool instructions
3. `AGENTS.md`
4. `.claude/CLAUDE.md`
5. `.claude/policies/`
6. `.claude/memory/`
7. `.claude/tasks/`
8. `.claude/agents/`
9. `.claude/skills/`

`AGENTS.md` is the shared contract. `.claude/CLAUDE.md` is a runtime adapter and must not override it.

## Component Layer Relationships (Tasks → Skills → Agents)

Tasks, skills, and agents form a bottom-up creation chain. This is a build-and-promotion relationship that describes how each layer is created from the one below it; it is not the conflict-resolution ranking in *Authority Order*, and it does not change that ranking.

- **Tasks (`.claude/tasks/`)** — the smallest unit of work. The agent automatically records and updates the work it executes here, so this layer is agent-maintained, not user-curated. The task packet keeps only the current state (goal, inputs, verification, completion criteria); execution logs and handoff go to `.context/` so the packet never accumulates stale history.
- **Skills (`.claude/skills/`)** — created by promoting a recurring task bundle. When the same bundle of tasks recurs and can be named by one higher-level name that covers every task in the bundle, that bundle is abstracted into a single reusable skill. The skill-quality bar (clear trigger, inputs, stable procedure, predictable output, quality checks, failure cases) decides whether a promotion is sound. Tasks reference a skill by name and inputs and never copy its procedure.
- **Agents (`.claude/agents/`)** — created when a specific skills package must be operated in an independent context. A subagent of the main skills-using agent owns and operates that package, takes its task input and verification criteria from `.claude/tasks/`, references the skills (never copying their procedures), and returns results to the task packet or `.context/agents/<agent-name>/`.

Creation chain: atomic work is auto-recorded as **Tasks** → a recurring task bundle that fits one covering name is promoted to a **Skill** → a specific skills package that needs an isolated context is wrapped in an **Agent**.

### Enforced Promotion Loop

The creation chain is not only a convention; deterministic hooks and a policy enforce its *trigger* while leaving authoring to judgment:

- `.claude/hooks/task_ledger.py` (PostToolUse) auto-records every executed action and every skill use (a `SKILL.md` read) to `.context/task-log/`. This makes "the agent records all executed work" a measured fact, not a promise. Semantic task signatures are appended through `task_ledger.py record-task` (driven by the `write-task` skill).
- `.claude/hooks/detect_promotions.py` (PostToolUse and SessionStart) evaluates the ledger against `.claude/policies/promotion.json` and re-surfaces every qualifying candidate — after each action and at session start, so cross-session candidates appear immediately — until it is promoted or declined. It echoes the firing event name back in `hookSpecificOutput.hookEventName` as Claude Code requires.
- Concrete conditions live in `.claude/policies/promotion.json`. Defaults: a **skill** candidate is a task signature recurring at least `min_recurrence` times across at least `min_distinct_sessions` sessions and not already a skill; an **agent** candidate is a skills package co-used at least `min_cousage` times across at least `min_distinct_sessions` sessions and not already owned by an agent.
- Authoring stays a judgment step: a surfaced skill candidate is built with `write-skill`, an agent candidate with `write-subagent`, and each candidate is closed with `detect_promotions.py resolve` (`--decision promote` or `--decision decline`). Agent-package detection is fully deterministic; skill detection relies on the recorded task signatures.

## Memory Derivation Relationship (Memory → User Preferences / Terminology)

`.claude/memory/memory.md` holds broad durable facts. Two narrower stores specialize it: `.claude/memory/user_preferences.md` (stable, project-scoped preferences) and `.claude/memory/word.json` (the terminology dictionary). When a durable fact is really a stable preference or a recurring term, it should be *derived* out of the broad store into the specific one. This is a derivation relationship, not the conflict-resolution ranking in *Authority Order*.

### Enforced Derivation Loop

The same enforced-trigger / judgment-authoring split that governs promotion also governs derivation:

- `.claude/hooks/detect_derivations.py` (PostToolUse and SessionStart) evaluates two deterministic signal sources against `.claude/policies/derivation.json` and re-surfaces every qualifying candidate until it is derived or declined. It echoes the firing event name back in `hookSpecificOutput.hookEventName` as Claude Code requires, exactly like `detect_promotions.py`.
- **Explicit memory markers** — a `memory.md` entry may carry an optional `Derive: preference` or `Derive: term: <word>` line. Such an entry is an explicit, already-qualifying signal and surfaces immediately. This is the literal "memory → derive" bridge.
- **Recorded observations** — `detect_derivations.py record-signal --kind {preference,term} --key <key> --session <id>` appends a semantic observation to `.context/memory-log/signals.jsonl`. A key recurring at least `min_recurrence` times across at least `min_distinct_sessions` sessions qualifies on the threshold, mirroring how task signatures drive skill promotion.
- Concrete conditions live in `.claude/policies/derivation.json`; a candidate already present in `user_preferences.md` (preference) or `word.json` (term) is skipped.
- Authoring stays a judgment step: a preference candidate is written into `user_preferences.md` (confirm it is stable and project-scoped first), a term candidate is registered with the `register-term` skill (confirm the four fields with the user; never invent a definition), and each candidate is closed with `detect_derivations.py resolve` (`--decision promote` or `--decision decline`).

## Initial Local Agent Setup

When the user copies this folder to create a local agent project, use the `agent-clone-setup` skill in `--project-setup` mode first. That mode rewrites `AGENTS.md` and `.claude/CLAUDE.md` for the actual agent role and can update `.claude/policies/agent-workspace.json`.

Do not create `.context/agents/` bootstrap packets or `.claude/agents/` subagent files unless the user explicitly asks for a cloned subagent.

## Canonical Files

Use these paths exactly. If a file is missing, do not invent its contents; continue with available context and report the gap only when it affects the task.

| Component | Path | Role |
| --- | --- | --- |
| Shared contract | `AGENTS.md` | Cross-agent rules, component roles, I/O protocol |
| Claude adapter | `.claude/CLAUDE.md` | Claude-specific execution and response rules |
| Claude settings | `.claude/settings.json` | Shared Claude Code settings, hooks, plugin defaults, and memory mode |
| Claude hooks | `.claude/hooks/` | Deterministic guard and validation scripts called by `.claude/settings.json` |
| Claude agents | `.claude/agents/` | Subagents that own a specific skills package in an independent context, plus the generated agent index |
| Agent policies | `.claude/policies/` | Machine-readable policy files consumed by project hooks |
| Project memory | `.claude/memory/memory.md` | Durable context and accepted decisions |
| User preferences | `.claude/memory/user_preferences.md` | Stable project-scoped preferences |
| Terminology | `.claude/memory/word.json` | Machine-readable term dictionary, managed by the `register-term` skill |
| Skill registry | `.claude/skills/skills.md` | Reusable procedures promoted from recurring task bundles |
| Task registry | `.claude/tasks/tasks.md` | Agent-maintained current task packet (smallest unit of work) |

## Component I/O Contracts

| Component | Reads / takes in | Produces | Write rule |
| --- | --- | --- | --- |
| `AGENTS.md` | User request, workspace rules, file tree when structure matters | Stable rules, canonical paths, read/write/handoff rules | Update only when a component contract changes. Keep project-neutral. No preferences, task progress, or domain content. |
| `.claude/CLAUDE.md` | `AGENTS.md`, user request, files in read order | Claude execution loop, response format, file-update discipline | Keep synchronized with `AGENTS.md`. No domain-specific assumptions. |
| `.claude/settings.json` | Claude Code runtime settings and hook registrations | Shared project defaults for plugins, hooks, memory mode, and permissions | Keep project-neutral. Shared settings keep `autoMemoryEnabled` disabled so checked-in `.claude/memory/` remains the canonical project memory. Re-enable auto memory only in a project-specific fork or local settings with explicit storage scope. |
| `.claude/hooks/` | Claude Code hook JSON on stdin, project files, validation scripts | Non-interactive guard and validation behavior | Keep scripts deterministic, project-neutral, and safe to run repeatedly. Do not put domain content or task progress here. |
| `.claude/agents/` | A specific skills package that needs an independent context, plus its trigger, tool scope, and handoff expectations | One Markdown file per Claude subagent plus generated `agents.md` index | Create only when a skills package must run in an isolated context. Keep reusable and project-neutral. Reference skills, do not copy their procedures. Do not store task progress here. Align agent `name` values with `.claude/policies/agent-workspace.json` only when the agent has a path or Bash boundary. Do not hand-edit the generated index section. |
| `.claude/policies/` | Hook-readable project policy such as agent workspace boundaries (`agent-workspace.json`), promotion conditions (`promotion.json`), memory derivation conditions (`derivation.json`), and inter-agent feedback routing (`feedback.json`; design in `FEEDBACK.md`) | Valid JSON policy files and short operating notes | Keep policy data deterministic and machine-readable. Do not store secrets, personal preferences, task progress, or domain content here. |
| `.claude/memory/memory.md` | Confirmed durable facts, accepted decisions, stable constraints | Short dated entries reusable later | Store only confirmed, likely-to-matter facts. No temporary progress or guesses. This checked-in file is the canonical shared project memory; Claude auto memory is disabled in shared settings by default. A fact that is really a stable preference or a recurring term carries an optional `Derive:` marker so `detect_derivations.py` surfaces it for moving into `user_preferences.md` or `word.json`. |
| `.claude/memory/user_preferences.md` | Explicit preferences, repeated stable choices | Project-scoped preferences for style, output, review level | Write only when the user explicitly states a preference, it is repeated and stable, and it applies to this project. No personal profiles or sensitive data. Task-local preferences go in `.claude/tasks/tasks.md`. Preference candidates are surfaced by `detect_derivations.py` (from `memory.md` `Derive:` markers or recorded signals) and closed with its `resolve` subcommand. |
| `.claude/memory/word.json` | Terms, abbreviations, translations, definitions | Valid JSON dictionary entries | Keep valid JSON, no comments. Each entry uses `term`, `ko`, `definition`, `use_when`. Add or update through the `register-term` skill (it validates fields and blocks duplicates); do not hand-edit ad hoc. Direct Claude file edits are blocked by the project hook, and Bash changes are revalidated after tool use. This dictionary is meant to be grown actively: when a project-specific term recurs and is not yet recorded, proactively propose adding it, confirm the four fields with the user, then register — never invent a definition. Recurring unregistered terms are surfaced as candidates by `detect_derivations.py`. |
| `.claude/skills/` | A recurring task bundle that fits one covering name, with trigger, inputs, procedure, output, failure cases | Reusable skill folders, each with a `SKILL.md`; `.claude/skills/skills.md` is the generated English index | Create by promoting a recurring task bundle into one named, reusable skill. Methods only, not task logs. One skill per folder; use the `write-skill` skill and its template; let the `ConfigChange` project hook regenerate the index. |
| `.claude/tasks/tasks.md` | Executed work, objective, inputs, expected output, completion criteria | Agent-maintained current task packet (smallest unit of work) with status and verification | Agent-maintained, not user-curated. The packet holds the current state only; execution logs and handoff go to `.context/`, durable facts to `.claude/memory/`. Mark uncertainty instead of assuming. |

## Standard Formats

Skill-owned templates are the single source of truth. Other files reference them rather than redefining them.

### Skill Folder — `.claude/skills/<name>/`

One skill per folder. `SKILL.md` is the only required file and must list every other file and subfolder under `내부 자원`. Use `.claude/skills/write-skill/SKILL.md`; its template lives at `.claude/skills/write-skill/templates/SKILL.md`.

### Task Packet — `.claude/tasks/tasks.md`

Use `.claude/skills/write-task/SKILL.md`; its template lives at `.claude/skills/write-task/templates/task.md`.

### Agent File — `.claude/agents/<name>.md`

One Claude subagent per Markdown file. Use `.claude/skills/write-subagent/SKILL.md`; its template lives at `.claude/skills/write-subagent/templates/AGENT.md`. The YAML `name` must be stable; if the agent has a workspace boundary, use the same name under `.claude/policies/agent-workspace.json`.

### Memory Entry — `.claude/memory/memory.md`

```md
## YYYY-MM-DD - Short Title

Fact:
Source:
Use Later When:
Derive:   # optional — `preference` or `term: <word>` to surface a derivation candidate
```

`Derive:` is optional and backward-compatible. Omit it for an ordinary durable fact. Set `Derive: preference` when the fact is really a stable preference, or `Derive: term: <word>` when it names a recurring term; `detect_derivations.py` then surfaces it for moving into `user_preferences.md` or `word.json` (via the `register-term` skill).

### Final Response

```md
## Result
What changed or what was produced.

## Notes
Important caveats, verification, or file paths.

## Next Step
Only when a natural next action exists.
```

For small requests, shorten the format instead of forcing headings.

## File Update Rules

- Keep changes scoped to the request.
- Do not modify secrets, private notes, raw datasets, `.env` files, PDFs, or final deliverables unless asked.
- Read user-created content before overwriting it.
- Preserve existing structure unless the structure itself is the problem.
- When renaming or replacing files, update all internal references in the same pass.

## Project-Neutrality Rules

- Do not assume a research field, method, dataset, institution, or publication target.
- Keep project-specific facts in the project that uses the template, not here.
- The only durable fact this template preserves is how components exchange inputs and outputs.
