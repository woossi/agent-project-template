#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPT = REPO_ROOT / ".claude/skills/agent-clone-setup/scripts/init_agent_clone.py"


def valid_payload() -> dict:
    return {
        "agent_name": "reviewer-a",
        "source_agent": "reviewer-template",
        "clone_purpose": "Review scoped documentation changes",
        "role": "Read the assigned files and return risks only",
        "task_objective": "Find contract drift in template docs",
        "inputs": ["AGENTS.md", ".claude/CLAUDE.md"],
        "allowed_paths": ["AGENTS.md", ".claude/**"],
        "denied_paths": [".env", "data/raw/**"],
        "tools": ["Read", "Grep", "Glob"],
        "outputs": ["findings with file anchors"],
        "handoff_path": ".context/agents/reviewer-a",
        "verification": ["all findings have file anchors"],
        "constraints": ["do not edit files"],
        "initial_notes": ["focus on reusable template contracts"],
        "bash": {"allow": ["rg *"], "deny": ["rm *"]},
    }


class InitAgentCloneTest(unittest.TestCase):
    def run_script(
        self,
        project_root: Path,
        payload: dict,
        *extra_args: str,
    ) -> subprocess.CompletedProcess[str]:
        input_path = project_root / "clone-input.json"
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--project-root",
                str(project_root),
                "--input",
                str(input_path),
                *extra_args,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_creates_bootstrap_and_canonical_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_script(root, valid_payload())
            bootstrap = root / ".context/agents/reviewer-a/bootstrap.md"
            canonical = root / ".context/agents/reviewer-a/clone-input.json"

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(bootstrap.exists())
            self.assertTrue(canonical.exists())
            text = bootstrap.read_text(encoding="utf-8")
            self.assertIn("reviewer-a", text)
            self.assertIn("Required Brief", text)
            self.assertIn("AGENTS.md", text)

    def test_missing_required_field_fails_without_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = valid_payload()
            payload.pop("role")

            result = self.run_script(root, payload)

            self.assertEqual(result.returncode, 2)
            self.assertIn("missing required field: role", result.stderr)
            self.assertFalse((root / ".context/agents/reviewer-a").exists())

    def test_update_policy_adds_agent_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy_path = root / ".claude/policies/agent-workspace.json"
            policy_path.parent.mkdir(parents=True)
            policy_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "defaults": {"allow": ["."], "deny": [], "bash": {"allow": [], "deny": []}},
                        "agents": {},
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_script(root, valid_payload(), "--update-policy")

            self.assertEqual(result.returncode, 0, result.stderr)
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            self.assertEqual(policy["agents"]["reviewer-a"]["allow"], ["AGENTS.md", ".claude/**"])
            self.assertEqual(policy["agents"]["reviewer-a"]["deny"], [".env", "data/raw/**"])
            self.assertEqual(policy["agents"]["reviewer-a"]["bash"]["allow"], ["rg *"])


if __name__ == "__main__":
    unittest.main()
