# Agent Index

Project-scoped Claude subagents live in this directory. Each subagent is a Markdown file with YAML frontmatter.
The **Files** section is a human-maintained index; Claude Code discovers subagents directly from the `*.md` files here.

## Files

| Path | Role |
| --- | --- |
| `.claude/agents/agents.md` | Human-readable index and maintenance note |
| `.claude/agents/figure-designer.md` | Use when a non-spatial publication-quality academic figure or statistical plot needs to be generated or refined in an isolated context via the PaperBanana MCP server (conceptual diagrams, pipeline/architecture figures, framework illustrations, bar/line/scatter/box statistical plots). Not for GIS/spatial maps — those go to gis-figure-designer. manuscript-writer or data-curator delegates one figure request at a time. |
| `.claude/agents/section-writer.md` | Use when a single manuscript section (introduction, related work, methods, results, discussion, or abstract) needs focused drafting or rewriting in an isolated context, applying the academic-writing skill. manuscript-writer delegates one section at a time. |

## Maintenance

- Keep one subagent per Markdown file.
- Create a subagent only when a specific skills package needs an independent context; it owns and operates that package, references skills, and never copies their procedures.
- Update the Files table by hand in the same change that adds or removes a subagent.
- Start new subagents with `.claude/skills/write-subagent/templates/AGENT.md`.
- Keep the `name` field aligned with `.claude/policies/agent-workspace.json` when the subagent has a restricted workspace.
- Put task handoff notes in `.context/agents/<agent-name>/`, not in the subagent definition.
- Clone initialization is governed by `.claude/skills/agent-clone-setup/SKILL.md`; do not hand-roll clone bootstrap packets.
