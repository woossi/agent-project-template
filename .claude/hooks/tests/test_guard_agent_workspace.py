#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / ".claude/hooks/guard_agent_workspace.py"


class GuardAgentWorkspaceTest(unittest.TestCase):
    def run_hook(
        self,
        root: Path,
        policy: dict,
        payload: dict,
        *,
        agent_name: str = "writer",
    ) -> subprocess.CompletedProcess[str]:
        policy_path = root / ".claude/policies/agent-workspace.json"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(json.dumps(policy), encoding="utf-8")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(root)
        env["CLAUDE_AGENT_NAME"] = agent_name
        env["CLAUDE_AGENT_WORKSPACE_POLICY"] = str(policy_path)

        return subprocess.run(
            [sys.executable, str(HOOK), "--policy", str(policy_path)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_allows_file_path_inside_agent_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_hook(
                root,
                {
                    "version": 1,
                    "defaults": {"allow": ["."], "deny": []},
                    "agents": {"writer": {"allow": ["docs/**"], "deny": []}},
                },
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "tool_input": {"file_path": "docs/notes.md"},
                },
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_blocks_file_path_outside_agent_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_hook(
                root,
                {
                    "version": 1,
                    "defaults": {"allow": ["."], "deny": []},
                    "agents": {"writer": {"allow": ["docs/**"], "deny": []}},
                },
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Edit",
                    "tool_input": {"file_path": "src/app.py"},
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("outside allowed workspace", result.stderr)

    def test_allows_absolute_path_when_explicitly_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as external:
            root = Path(tmp)
            knowledge = Path(external) / "knowledge"
            result = self.run_hook(
                root,
                {
                    "version": 1,
                    "defaults": {"allow": ["."], "deny": []},
                    "agents": {
                        "writer": {
                            "allow": ["docs/**", str(knowledge / "**")],
                            "deny": [],
                        }
                    },
                },
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Read",
                    "tool_input": {"file_path": str(knowledge / "graph.md")},
                },
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_blocks_denied_path_even_when_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_hook(
                root,
                {
                    "version": 1,
                    "defaults": {"allow": ["."], "deny": []},
                    "agents": {
                        "writer": {
                            "allow": ["docs/**"],
                            "deny": ["docs/private/**"],
                        }
                    },
                },
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "tool_input": {"file_path": "docs/private/notes.md"},
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("denied by workspace policy", result.stderr)

    def test_bash_allowlist_blocks_unlisted_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_hook(
                root,
                {
                    "version": 1,
                    "defaults": {"allow": ["."], "deny": []},
                    "agents": {
                        "writer": {
                            "allow": ["docs/**"],
                            "deny": [],
                            "bash": {"allow": ["rg *", "sed *"], "deny": []},
                        }
                    },
                },
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "tool_input": {"command": "python3 scripts/build.py"},
                },
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Bash command is not allowed", result.stderr)


if __name__ == "__main__":
    unittest.main()
