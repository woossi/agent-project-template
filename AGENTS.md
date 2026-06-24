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
| Claude agents | `.claude/agents/` | Project-scoped Claude subagent definitions and generated agent index |
| Agent policies | `.claude/policies/` | Machine-readable policy files consumed by project hooks |
| Project memory | `.claude/memory/memory.md` | Durable context and accepted decisions |
| User preferences | `.claude/memory/user_preferences.md` | Stable project-scoped preferences |
| Terminology | `.claude/memory/word.json` | Machine-readable term dictionary, managed by the `register-term` skill |
| Skill registry | `.claude/skills/skills.md` | Reusable procedures |
| Task registry | `.claude/tasks/tasks.md` | Current task packet |

## Component I/O Contracts

| Component | Reads / takes in | Produces | Write rule |
| --- | --- | --- | --- |
| `AGENTS.md` | User request, workspace rules, file tree when structure matters | Stable rules, canonical paths, read/write/handoff rules | Update only when a component contract changes. Keep project-neutral. No preferences, task progress, or domain content. |
| `.claude/CLAUDE.md` | `AGENTS.md`, user request, files in read order | Claude execution loop, response format, file-update discipline | Keep synchronized with `AGENTS.md`. No domain-specific assumptions. |
| `.claude/settings.json` | Claude Code runtime settings and hook registrations | Shared project defaults for plugins, hooks, memory mode, and permissions | Keep project-neutral. Shared settings keep `autoMemoryEnabled` disabled so checked-in `.claude/memory/` remains the canonical project memory. Re-enable auto memory only in a project-specific fork or local settings with explicit storage scope. |
| `.claude/hooks/` | Claude Code hook JSON on stdin, project files, validation scripts | Non-interactive guard and validation behavior | Keep scripts deterministic, project-neutral, and safe to run repeatedly. Do not put domain content or task progress here. |
| `.claude/agents/` | Repeated project role, trigger, tool scope, and handoff expectations | One Markdown file per Claude subagent plus generated `agents.md` index | Keep reusable and project-neutral. Do not store task progress here. Align agent `name` values with `.claude/policies/agent-workspace.json` only when the agent has a path or Bash boundary. Do not hand-edit the generated index section. |
| `.claude/policies/` | Hook-readable project policy such as agent workspace boundaries | Valid JSON policy files and short operating notes | Keep policy data deterministic and machine-readable. Do not store secrets, personal preferences, task progress, or domain content here. |
| `.claude/memory/memory.md` | Confirmed durable facts, accepted decisions, stable constraints | Short dated entries reusable later | Store only confirmed, likely-to-matter facts. No temporary progress or guesses. This checked-in file is the canonical shared project memory; Claude auto memory is disabled in shared settings by default. |
| `.claude/memory/user_preferences.md` | Explicit preferences, repeated stable choices | Project-scoped preferences for style, output, review level | No personal profiles or sensitive data. Task-local preferences go in `.claude/tasks/tasks.md`. |
| `.claude/memory/word.json` | Terms, abbreviations, translations, definitions | Valid JSON dictionary entries | Keep valid JSON, no comments. Each entry uses `term`, `ko`, `definition`, `use_when`. Add or update through the `register-term` skill (it validates fields and blocks duplicates); do not hand-edit ad hoc. Direct Claude file edits are blocked by the project hook, and Bash changes are revalidated after tool use. This dictionary is meant to be grown actively: when a project-specific term recurs and is not yet recorded, proactively propose adding it, confirm the four fields with the user, then register — never invent a definition. |
| `.claude/skills/` | A repeated workflow with trigger, inputs, procedure, output, failure cases | Reusable skill folders, each with a `SKILL.md`; `.claude/skills/skills.md` is the generated English index | Reusable methods only, not task logs. One skill per folder; use the `write-skill` skill and its template; let the `ConfigChange` project hook regenerate the index. |
| `.claude/tasks/tasks.md` | User request, objective, inputs, expected output, completion criteria | Current task packet with status and verification | Current work only, not durable memory. Mark uncertainty instead of assuming. |

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
```

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
