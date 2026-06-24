# .claude/CLAUDE.md

@../AGENTS.md

## Role

Claude runtime adapter for this agent-template project. The shared `AGENTS.md` contract is imported above; this file only adds Claude-specific application of that contract.

Default language is Korean unless the deliverable requires otherwise.

## Operating Principle

Optimize for reusable, verifiable work. Do not add project-specific domains, datasets, methods, or goals unless the user explicitly asks for a project-specific adaptation.

## Startup Read Order

At the start of a non-trivial task, read in this order — only the smallest useful portion of each, and skip unrelated context for simple tasks:

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/memory/memory.md`
4. `.claude/memory/user_preferences.md`
5. `.claude/memory/word.json`
6. `.claude/tasks/tasks.md`
7. `.claude/skills/skills.md` — **read only the "Skill Index" table** to see what skills exist. Do not load any skill's body upfront.

Skill loading is lazy: from the index, open a skill's `SKILL.md` only when its trigger matches the task, and read its internal files (code, references) only when that step runs. Read the format/registry sections of `skills.md` only when creating a new skill.

## Input Normalization

Before acting, frame the request internally as: User Request, Needed Output, Available Inputs, Missing Inputs (only blocking ones), Applicable Skill, Write Targets. Expose this packet only when it helps the user; otherwise use it to keep execution consistent.

## Execution Loop

1. Identify the component being changed (`AGENTS.md`, `.claude/CLAUDE.md`, `.claude/memory/`, `.claude/skills/`, `.claude/tasks/`).
2. Confirm its expected input and output (see `AGENTS.md` I/O contracts).
3. Read the file before editing.
4. Make the smallest complete change.
5. Update cross-references when paths or contracts change.
6. Verify Markdown structure, JSON validity, and path references.
7. Report changed files and verification.

## Component Handling

Apply the write rules in the `AGENTS.md` I/O table. Before writing, check the gate for each component:

- **`AGENTS.md`** — shared rules only. Keep out personal profiles, task progress, domain facts, and one-off notes.
- **`.claude/CLAUDE.md`** — Claude-specific execution only. Cross-agent rules belong in `AGENTS.md`, mirrored here only as Claude-specific application.
- **`.claude/memory/memory.md`** — write only if the fact is confirmed, future-relevant, project-scoped, and free of sensitive content. Otherwise skip.
- **`.claude/memory/user_preferences.md`** — stable project-scoped preferences only (output format, review standard, confirmed terminology). Not one-time requests, sensitive facts, or personality claims.
- **`.claude/memory/word.json`** — must stay valid JSON with the `term`/`ko`/`definition`/`use_when` shape. Manage it through the `register-term` skill rather than editing by hand, so fields are validated and duplicates are blocked. Treat it as an actively maintained resource: when a project-specific term recurs and is missing, proactively offer to register it and confirm the four fields with the user first — do not guess a definition.
- **`.claude/skills/`** — reusable methods only, never one-time tasks. One skill per folder (`.claude/skills/<name>/SKILL.md`); copy `.claude/skills/_template/` and let the project hook regenerate `.claude/skills/skills.md`.
- **`.claude/tasks/tasks.md`** — current work only, never durable memory.

For the standard formats (task packet, skill record, memory entry, final response), use the templates in `AGENTS.md`.

## Response Rules

For normal work, use the Final Response format in `AGENTS.md` (Result / Notes / Next Step). For code or file edits, include files changed, verification performed, and anything not done. For very small requests, answer directly without forcing headings.

## Clarification Rules

Ask only when the answer is required and cannot be safely inferred. If partial progress is safe, proceed within the clear boundary and mark uncertainty.

## Verification Rules

Before claiming completion:

- Canonical paths match between `AGENTS.md` and `.claude/CLAUDE.md`.
- `.claude/memory/word.json` passes `register-term --check` (valid JSON, required fields present, no duplicate terms) after any terminology change.
- No stale references to renamed files.
- Final diff contains no unintended project-specific content.

## Final Principle

Keep the template focused on component I/O. Projects can add their own domain context; this folder stays the reusable contract layer.
