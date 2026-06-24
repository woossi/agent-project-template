# Skills

This file is the generated skill index. Each skill lives in its own folder
(`skills/<name>/`) and must include a `SKILL.md` file.

Read only the **Skill Index** table at startup. Open a skill's `SKILL.md` only
when the request clearly matches that workflow. The detailed skill documents
are written in Korean for human editing; this index stays English because it is
automatically managed.

> The `update-skill-index` hook manages this file automatically when a skill
> `SKILL.md` changes.

## Skill Index

| Skill | Folder | Load rule |
| --- | --- | --- |
| register-term | `register-term/` | Open `register-term/SKILL.md` only when the request clearly matches the `register-term` workflow. |
| update-skill-index | `update-skill-index/` | Open `update-skill-index/SKILL.md` only when the request clearly matches the `update-skill-index` workflow. |

---

## Skill Authoring Rules

Read this section only when creating or restructuring a skill.

### When To Create A Skill

Create a skill only for a reusable workflow with all of these properties:
repeated trigger, clear inputs, stable procedure, predictable output format,
quality checks, and known failure cases.

One-off tasks, progress logs, and durable facts are not skills.

### Fixed Folder Structure

```text
skills/
  skills.md            # generated index file
  _template/           # template copied when creating a new skill
  <skill-name>/        # one skill = one folder, English kebab-case
    SKILL.md           # required: Korean human-authored skill body
    <free files/folders>
```

- Use one folder per skill.
- Use English kebab-case for the folder name because the generated index uses
  folder names as English routing signals.
- `SKILL.md` must list every file and subfolder under "내부 자원".
- Start new skills by copying `_template/`.
- Do not edit the Skill Index table by hand; the project hook regenerates it.
- If a folder is deleted or renamed, update references in the same change.

### SKILL.md Template

The canonical human-authored skill template is in `_template/SKILL.md`. Keep
that template Korean so people can write and review skill procedures directly.
