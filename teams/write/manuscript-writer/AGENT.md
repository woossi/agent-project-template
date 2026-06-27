# Agent: manuscript-writer

Role: 원고 작성 에이전트: SSCR Q1 기준에 맞춰 논문 파트별(서론·관련연구·방법·결과·논의) 글을 작성·재작성하고 LaTeX 원고를 정련한다

Launch: `export CLAUDE_AGENT_NAME=manuscript-writer` then run `claude` from this folder.

Shared (symlinked to team root, identical across peers): .claude/{hooks,policies,skills,settings.json,CLAUDE.md}, AGENTS.md.
Private (this agent only): .claude/memory, .claude/tasks, .context.
