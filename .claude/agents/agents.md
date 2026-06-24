# Agent Index

Project-scoped Claude subagents live in this directory. Each subagent is a Markdown file with YAML frontmatter.

## Files

| Path | Role |
| --- | --- |
| `.claude/agents/_template/AGENT.md` | Template for a new project subagent |
| `.claude/agents/agents.md` | Human-readable index and maintenance note |

## Maintenance

- Keep one subagent per Markdown file.
- Keep the `name` field aligned with `.claude/policies/agent-workspace.json` when the subagent has a restricted workspace.
- Put task handoff notes in `.context/agents/<agent-name>/`, not in the subagent definition.
