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


class DenyReadDropOffTest(GuardAgentWorkspaceTest):
    """deny_read: a drop-off slot (other team's inbox) is WRITE-OK but READ-blocked.

    Models the team-only inbox: a worker may POST to another team (write) yet never
    READ that team's mailbox (no context bleed). The same path in plain ``deny`` blocks both.
    """

    POLICY = {
        "version": 1,
        "defaults": {"allow": ["."], "deny": [], "bash": {"allow": [], "deny": []}},
        "agents": {
            "de": {
                "allow": ["."],
                "deny": ["teams/data/de/**"],            # own-folder peers etc: read+write blocked
                "deny_read": ["teams/write/.claude/inbox/**"],  # other team inbox: write-OK, read-NO
            },
            "mw": {"allow": ["."], "deny": []},
        },
    }

    def _payload(self, tool, path):
        return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"file_path": path}}

    def test_write_to_dropoff_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            r = self.run_hook(root, self.POLICY,
                              self._payload("Write", "teams/write/.claude/inbox/m1.json"),
                              agent_name="de")
            self.assertEqual(r.returncode, 0, r.stderr)  # drop-off write passes

    def test_read_of_dropoff_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            r = self.run_hook(root, self.POLICY,
                              self._payload("Read", "teams/write/.claude/inbox/m1.json"),
                              agent_name="de")
            self.assertEqual(r.returncode, 2)  # reading another team's mail is blocked
            self.assertIn("denied", r.stderr)

    def test_edit_of_dropoff_allowed(self):
        # Edit is a write tool → drop-off write allowed (must not be stricter than Write).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            r = self.run_hook(root, self.POLICY,
                              self._payload("Edit", "teams/write/.claude/inbox/m1.json"),
                              agent_name="de")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_plain_deny_blocks_both_read_and_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for tool in ("Read", "Write"):
                r = self.run_hook(root, self.POLICY,
                                  self._payload(tool, "teams/data/de/secret.txt"),
                                  agent_name="de")
                self.assertEqual(r.returncode, 2, f"{tool} should be blocked by plain deny")

    def test_unregistered_identity_blocks_dropoff_read_and_write(self):
        # fail-closed: an unidentified caller gets the STRICTER rule — deny_read folded into
        # deny, so even WRITE to a drop-off is blocked (no lenient exception for unknowns).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for tool in ("Read", "Write"):
                r = self.run_hook(root, self.POLICY,
                                  self._payload(tool, "teams/write/.claude/inbox/m1.json"),
                                  agent_name="ghost-typo")
                self.assertEqual(r.returncode, 2, f"unregistered {tool} must be blocked")


if __name__ == "__main__":
    unittest.main()
