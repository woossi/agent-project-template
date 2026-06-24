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

## Default: allow every tool inside the workspace

The shipped defaults grant every tool inside the project root, and that is the
intended baseline — keep it permissive so ordinary commands are not blocked.

- `allow: ["."]` lets path tools (Read/Edit/Write/MultiEdit) touch anything under
  the project root. `"."`, `"**"`, and `"**/*"` all mean "everywhere".
- `bash.allow: []` (empty) means **every Bash command is allowed**; the guard only
  enforces `bash.deny`. The moment `bash.allow` is non-empty it becomes a
  whitelist, so unlisted commands (`ls`, `cat`, `find`, …) get blocked. Leave it
  empty to allow all commands.
- Tools other than path tools and Bash are never blocked by this guard.

Restrict a specific agent only by adding an entry under `agents` (narrow `allow`,
extend `deny`, or set a `bash.allow` whitelist). Do not narrow `defaults`, or the
whole project loses access to normal tools.
