# Agent: orchestrator

Role: 백로그 분해·할당·완료 추적

Launch: `export CLAUDE_AGENT_NAME=orchestrator` then run `claude` from this folder.

Shared (symlinked to team root, identical across peers): .claude/{hooks,policies,skills,settings.json,CLAUDE.md}, AGENTS.md.
Private (this agent only): .claude/memory, .claude/tasks, .context.
