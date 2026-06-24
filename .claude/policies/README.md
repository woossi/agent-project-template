# Agent Workspace Policies

`agent-workspace.json` is the machine-readable policy used by `.claude/hooks/guard_agent_workspace.py`.

## Shape

```json
{
  "version": 1,
  "defaults": {
    "allow": ["."],
    "deny": [],
    "bash": {
      "allow": [],
      "deny": []
    }
  },
  "agents": {
    "agent-name": {
      "allow": ["src/**"],
      "deny": ["src/generated/**"],
      "bash": {
        "allow": ["rg *", "sed *"],
        "deny": []
      }
    }
  }
}
```

`allow` and `deny` are project-relative path globs. Agent entries override `defaults.allow`, extend `defaults.deny`, and can narrow Bash command usage with `bash.allow`.
