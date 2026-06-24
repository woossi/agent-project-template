# .claude/CLAUDE.md

@../AGENTS.md

## Role

Claude runtime adapter for this agent-template project. The shared `AGENTS.md` contract is imported above; this file only adds Claude-specific application of that contract.

## Operating Principle

Optimize for reusable, verifiable work. Do not add project-specific domains, datasets, methods, or goals unless the user explicitly asks for a project-specific adaptation.

## Component Handling

Apply the write rules in the `AGENTS.md` I/O table. Before writing, check the gate for each component:

- **`AGENTS.md`** — shared rules only. Keep out personal profiles, task progress, domain facts, and one-off notes.
- **`.claude/CLAUDE.md`** — Claude-specific execution only. Cross-agent rules belong in `AGENTS.md`, mirrored here only as Claude-specific application.
- **`.claude/settings.json`** — shared Claude Code defaults only. Keep `autoMemoryEnabled` disabled unless this template is intentionally forked for a project-specific memory storage policy. Register deterministic hooks here; do not add domain assumptions.
- **`.claude/hooks/`** — non-interactive hook scripts only. Keep them deterministic, project-neutral, idempotent, and safe to run repeatedly.
- **`.claude/agents/`** — project-scoped Claude subagents only. Keep each agent reusable, keep task progress in `.claude/tasks/` or `.context/`, and align bounded agent names with `.claude/policies/agent-workspace.json`.
- **`.claude/policies/`** — machine-readable project policy consumed by hooks. Keep JSON valid, deterministic, and free of secrets, personal preferences, task progress, and domain content.
- **`.claude/memory/memory.md`** — write only if the fact is confirmed, future-relevant, project-scoped, and free of sensitive content. Otherwise skip. This checked-in file is the canonical shared project memory; Claude auto memory is disabled by default in shared settings.
- **`.claude/memory/user_preferences.md`** — stable project-scoped preferences only (output format, review standard, confirmed terminology). Not one-time requests, sensitive facts, or personality claims.
- **`.claude/memory/word.json`** — must stay valid JSON with the `term`/`ko`/`definition`/`use_when` shape. Manage it through the `register-term` skill rather than editing by hand, so fields are validated and duplicates are blocked. Direct Claude file edits are blocked by the project hook, and Bash changes are revalidated after tool use. Treat it as an actively maintained resource: when a project-specific term recurs and is missing, proactively offer to register it and confirm the four fields with the user first — do not guess a definition.
- **`.claude/skills/`** — reusable methods only, never one-time tasks. One skill per folder (`.claude/skills/<name>/SKILL.md`); copy `.claude/skills/_template/` and let the `ConfigChange` project hook regenerate `.claude/skills/skills.md`.
- **`.claude/tasks/tasks.md`** — current work only, never durable memory.

## Final Principle

Keep the template focused on component I/O. Projects can add their own domain context; this folder stays the reusable contract layer.
