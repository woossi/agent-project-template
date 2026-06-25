# Skills

This file is the generated skill index. Each skill lives in its own folder
(`skills/<name>/`) and must include a `SKILL.md` file.

Read only the **Skill Index** table at startup. Open a skill's `SKILL.md` only
when the request clearly matches that workflow. The detailed skill documents
are written in Korean for human editing; this index stays English because it is
automatically managed.

> The ConfigChange hook (`.claude/hooks/update_skill_index.py`) manages this file
> automatically when Claude Code detects skill configuration changes.

## Skill Index

| Skill | Folder | Load rule |
| --- | --- | --- |
| agent-clone-setup | `agent-clone-setup/` | Open `agent-clone-setup/SKILL.md` only when the request clearly matches the `agent-clone-setup` workflow. |
| create-team-agent | `create-team-agent/` | Open `create-team-agent/SKILL.md` only when the request clearly matches the `create-team-agent` workflow. |
| give-feedback | `give-feedback/` | Open `give-feedback/SKILL.md` only when the request clearly matches the `give-feedback` workflow. |
| journal-submission-checklist | `journal-submission-checklist/` | Open `journal-submission-checklist/SKILL.md` only when the request clearly matches the `journal-submission-checklist` workflow. |
| process-feedback | `process-feedback/` | Open `process-feedback/SKILL.md` only when the request clearly matches the `process-feedback` workflow. |
| register-term | `register-term/` | Open `register-term/SKILL.md` only when the request clearly matches the `register-term` workflow. |
| reminders-team-bridge | `reminders-team-bridge/` | Open `reminders-team-bridge/SKILL.md` only when the request clearly matches the `reminders-team-bridge` workflow. |
| scholarly-evidence-search | `scholarly-evidence-search/` | Open `scholarly-evidence-search/SKILL.md` only when the request clearly matches the `scholarly-evidence-search` workflow. |
| set-team-goal | `set-team-goal/` | Open `set-team-goal/SKILL.md` only when the request clearly matches the `set-team-goal` workflow. |
| team-derive-author | `team-derive-author/` | Open `team-derive-author/SKILL.md` only when the request clearly matches the `team-derive-author` workflow. |
| team-inbox | `team-inbox/` | Open `team-inbox/SKILL.md` only when the request clearly matches the `team-inbox` workflow. |
| team-init | `team-init/` | Open `team-init/SKILL.md` only when the request clearly matches the `team-init` workflow. |
| write-skill | `write-skill/` | Open `write-skill/SKILL.md` only when the request clearly matches the `write-skill` workflow. |
| write-subagent | `write-subagent/` | Open `write-subagent/SKILL.md` only when the request clearly matches the `write-subagent` workflow. |
| write-task | `write-task/` | Open `write-task/SKILL.md` only when the request clearly matches the `write-task` workflow. |

---

## Skill Authoring Rules

Read this section only when creating or restructuring a skill.

### When To Create A Skill

Create a skill by promoting a recurring task bundle: when multiple tasks share
the same workflow and that bundle can be named by one higher-level name that
covers every task in it, abstract the bundle into a single reusable skill. This
bottom-up promotion from repeated task clusters is the key signal for skill
creation.

The promotion is sound only when the workflow also has all of these properties:
repeated trigger, clear inputs, stable procedure, predictable output format,
quality checks, and known failure cases.

One-off tasks, progress logs, and durable facts are not skills.

### Fixed Folder Structure

```text
skills/
  skills.md            # generated index file
  <skill-name>/        # one skill = one folder, English kebab-case
    SKILL.md           # required: Korean human-authored skill body
    <free files/folders>
```

- Use one folder per skill.
- Use English kebab-case for the folder name because the generated index uses
  folder names as English routing signals.
- `SKILL.md` must list every file and subfolder under "내부 자원".
- Start new skills with `write-skill` and `.claude/skills/write-skill/templates/SKILL.md`.
- Do not edit the Skill Index table by hand; the project hook regenerates it.
- If a folder is deleted or renamed, update references in the same change.

### SKILL.md Template

The canonical human-authored skill template is in
`write-skill/templates/SKILL.md`. Keep that template Korean so people can write
and review skill procedures directly.
