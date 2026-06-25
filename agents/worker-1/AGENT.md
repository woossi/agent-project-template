# Agent: worker-1

Role: 할당 작업 실행·진행 기록·완료 체크

Launch: `export CLAUDE_AGENT_NAME=worker-1` then run `claude` from this folder.

Shared (symlinked to team root, identical across peers): .claude/{hooks,policies,skills,settings.json,CLAUDE.md}, AGENTS.md.
Private (this agent only): .claude/memory, .claude/tasks, .context.
