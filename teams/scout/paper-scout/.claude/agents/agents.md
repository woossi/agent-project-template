# Agents

이 디렉토리는 `paper-scout` 정체성의 서브에이전트 정의를 담는다.

## Files

| Path | Role |
| --- | --- |
| `.claude/agents/agents.md` | Human-readable index and maintenance note |
| `.claude/agents/fulltext-grounder.md` | Use when paper-scout needs PDF full-text obtained and exact citation-grounding quotes extracted for a batch of newly adopted citation keys, in an isolated context — fetching the body (local PDF → OA → scrapling paywall bypass → OCR for scans), then extracting verbatim quote + page + claim-fit per key into a handoff table for manuscript-writer. |

## Maintenance

- Keep one subagent per Markdown file.
- Create a subagent only when a specific skills package needs an independent context; it references skills and never copies their procedures.
- Do not edit the Files table by hand; the project hook (`.claude/hooks/update_agent_index.py`) regenerates it.
- Keep the `name` field aligned with `.claude/policies/agent-workspace.json` when the subagent has a restricted workspace.
