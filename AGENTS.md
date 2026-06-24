# AGENTS.md

## Purpose

This folder is a reusable agent-project template. It fixes the roles and I/O rules for the components that future projects share:

- `AGENTS.md`, `.claude/CLAUDE.md`, `.claude/memory/`, `.claude/skills/`, `.claude/tasks/`
- `.claude/settings.json`, `.claude/hooks/`

Keep it project-neutral. Do not customize it to one topic, dataset, method, client, or publication target unless the user explicitly asks for a project-specific fork.

Default response language is Korean. Use another language only when the requested output requires it.

## Authority Order

When instructions conflict, follow this order:

1. Current user request
2. Higher-level workspace or tool instructions
3. `AGENTS.md`
4. `.claude/CLAUDE.md`
5. `.claude/memory/`
6. `.claude/tasks/`
7. `.claude/skills/`

`AGENTS.md` is the shared contract. `.claude/CLAUDE.md` is a runtime adapter and must not override it.

## Canonical Files

Use these paths exactly. If a file is missing, do not invent its contents; continue with available context and report the gap only when it affects the task.

| Component | Path | Role |
| --- | --- | --- |
| Shared contract | `AGENTS.md` | Cross-agent rules, component roles, I/O protocol |
| Claude adapter | `.claude/CLAUDE.md` | Claude-specific execution and response rules |
| Claude settings | `.claude/settings.json` | Shared Claude Code settings, hooks, plugin defaults, and memory mode |
| Claude hooks | `.claude/hooks/` | Deterministic guard and validation scripts called by `.claude/settings.json` |
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
| `.claude/memory/memory.md` | Confirmed durable facts, accepted decisions, stable constraints | Short dated entries reusable later | Store only confirmed, likely-to-matter facts. No temporary progress or guesses. This checked-in file is the canonical shared project memory; Claude auto memory is disabled in shared settings by default. |
| `.claude/memory/user_preferences.md` | Explicit preferences, repeated stable choices | Project-scoped preferences for style, output, review level | No personal profiles or sensitive data. Task-local preferences go in `.claude/tasks/tasks.md`. |
| `.claude/memory/word.json` | Terms, abbreviations, translations, definitions | Valid JSON dictionary entries | Keep valid JSON, no comments. Each entry uses `term`, `ko`, `definition`, `use_when`. Add or update through the `register-term` skill (it validates fields and blocks duplicates); do not hand-edit ad hoc. Direct Claude file edits are blocked by the project hook, and Bash changes are revalidated after tool use. This dictionary is meant to be grown actively: when a project-specific term recurs and is not yet recorded, proactively propose adding it, confirm the four fields with the user, then register — never invent a definition. |
| `.claude/skills/` | A repeated workflow with trigger, inputs, procedure, output, failure cases | Reusable skill folders, each with a `SKILL.md`; `.claude/skills/skills.md` is the generated English index | Reusable methods only, not task logs. One skill per folder; copy `.claude/skills/_template/` to start; let the `ConfigChange` project hook regenerate the index. |
| `.claude/tasks/tasks.md` | User request, objective, inputs, expected output, completion criteria | Current task packet with status and verification | Current work only, not durable memory. Mark uncertainty instead of assuming. |

## Default Work Cycle

For non-trivial work:

1. Interpret the request.
2. Read `AGENTS.md`, and `.claude/CLAUDE.md` when relevant.
3. Read only the smallest useful context from `.claude/memory/`, `.claude/tasks/`, `.claude/skills/`.
4. Normalize ambiguous or multi-step work into a task packet.
5. Use an existing skill only when its trigger fits.
6. Execute with scoped changes, then verify.
7. Update `.claude/tasks/`, `.claude/memory/`, or `.claude/skills/` only when the write rules above are met.
8. Report result, key notes, and a next step when useful.

## Standard Formats

These templates are the single source of truth. Other files reference them rather than redefining them.

### Task Packet — `.claude/tasks/tasks.md`

```md
# Task

## Status
pending | in_progress | blocked | complete

## Objective
One sentence describing the outcome.

## Background
Why this task is needed.

## Inputs
- Input file, data, prompt, or source

## Expected Output
- Concrete deliverable

## Process
1. Step

## Decisions Needed
- Decision or question

## Risks
- Risk or uncertainty

## Verification
- Check that proves the output is valid

## Completion Criteria
- Condition that makes the task complete
```

### Skill Folder — `.claude/skills/<name>/`

One skill per folder. `SKILL.md` is the only required file and must list every other file and subfolder under "Internal Resources". Copy `.claude/skills/_template/` to start; the index in `.claude/skills/skills.md` is regenerated by the `ConfigChange` project hook. The `SKILL.md` template is Korean and lives in `.claude/skills/_template/SKILL.md`; read it only when creating or restructuring a skill.

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
