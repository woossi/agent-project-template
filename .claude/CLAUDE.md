# .claude/CLAUDE.md

@../AGENTS.md

## Role

Claude runtime adapter for this agent-template project. The shared `AGENTS.md` contract is imported above; this file only adds Claude-specific application of that contract.

## Operating Principle

Optimize for reusable, verifiable work. Do not add project-specific domains, datasets, methods, or goals unless the user explicitly asks for a project-specific adaptation.

If the user asks to turn this folder into a local agent project, use `agent-clone-setup` in `--project-setup` mode. Create `.context/agents/` bootstrap packets or `.claude/agents/` subagent files only when the user explicitly asks for a cloned subagent.

## Component Handling

Apply the write rules in the `AGENTS.md` I/O table, and respect the Tasks → Skills → Agents creation chain defined in `AGENTS.md` (*Component Layer Relationships*): tasks are auto-recorded atomic work, skills are recurring task bundles promoted under one covering name, and agents wrap a specific skills package in an independent context. The chain's trigger is enforced by `.claude/hooks/task_ledger.py` and `.claude/hooks/detect_promotions.py` against `.claude/policies/promotion.json` (see *Enforced Promotion Loop* in `AGENTS.md`); authoring the surfaced candidate stays a judgment step. Before writing, check the gate for each component:

- **`AGENTS.md`** — shared rules only. Keep out personal profiles, task progress, domain facts, and one-off notes.
- **`.claude/CLAUDE.md`** — Claude-specific execution only. Cross-agent rules belong in `AGENTS.md`, mirrored here only as Claude-specific application.
- **`.claude/settings.json`** — shared Claude Code defaults only. Keep `autoMemoryEnabled` disabled unless this template is intentionally forked for a project-specific memory storage policy. Register deterministic hooks here; do not add domain assumptions.
- **`.claude/hooks/`** — non-interactive hook scripts only. Keep them deterministic, project-neutral, idempotent, and safe to run repeatedly.
- **`.claude/agents/`** — subagents that own a specific skills package in an independent context. Create one only when a skills package needs isolated context. Reference skills, never copy their procedures. Keep each agent reusable, keep task progress in `.claude/tasks/` or `.context/`, and align bounded agent names with `.claude/policies/agent-workspace.json`.
- **`.claude/policies/`** — machine-readable project policy consumed by hooks. Keep JSON valid, deterministic, and free of secrets, personal preferences, task progress, and domain content. `promotion.json` holds the concrete skill/agent promotion conditions read by `detect_promotions.py`; `derivation.json` holds the memory→preference/term derivation conditions read by `detect_derivations.py`. Tune thresholds there rather than in the hook code.
- **`.claude/memory/memory.md`** — write only if the fact is confirmed, future-relevant, project-scoped, and free of sensitive content. Otherwise skip. This checked-in file is the canonical shared project memory; Claude auto memory is disabled by default in shared settings. When a durable fact is really a stable preference or a recurring term, add an optional `Derive: preference` / `Derive: term: <word>` line so `detect_derivations.py` surfaces it for moving into the dedicated store; act on the surfaced candidate and close it with `detect_derivations.py resolve`.
- **`.claude/memory/user_preferences.md`** — stable project-scoped preferences only (output format, review standard, confirmed terminology). Write only when the user explicitly states a preference, it is repeated and stable, and it applies to this project. Not one-time requests, sensitive facts, or personality claims. `detect_derivations.py` surfaces preference candidates from `memory.md` markers or recorded signals; author the entry here and resolve the candidate.
- **`.claude/memory/word.json`** — must stay valid JSON with the `term`/`ko`/`definition`/`use_when` shape. Manage it through the `register-term` skill rather than editing by hand, so fields are validated and duplicates are blocked. Direct Claude file edits are blocked by the project hook, and Bash changes are revalidated after tool use. Treat it as an actively maintained resource: when a project-specific term recurs and is missing, proactively offer to register it and confirm the four fields with the user first — do not guess a definition. `detect_derivations.py` surfaces recurring unregistered terms as candidates.
- **`.claude/skills/`** — reusable methods only, never one-time tasks. Promote a skill when a recurring task bundle fits one covering name. One skill per folder (`.claude/skills/<name>/SKILL.md`); use `write-skill` and let the `ConfigChange` project hook regenerate `.claude/skills/skills.md`.
- **`.claude/tasks/tasks.md`** — agent-maintained current work only, not user-curated and never durable memory. The packet holds the current state; execution logs and handoff go to `.context/`. The `task_ledger.py` hook auto-records executed actions and skill use to `.context/task-log/`; record a semantic task signature with `task_ledger.py record-task` when finishing a unit of work so `detect_promotions.py` can see recurring bundles. Act on any candidate it surfaces (`write-skill`/`write-subagent`) and close it with `detect_promotions.py resolve`.

## Final Principle

Keep the template focused on component I/O. Projects can add their own domain context; this folder stays the reusable contract layer.
