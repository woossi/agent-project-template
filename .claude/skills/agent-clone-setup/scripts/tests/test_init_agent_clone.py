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


def project_setup_payload() -> dict:
    return {
        "agent_name": "knowledge-base-manager",
        "agent_purpose": "지식 DB 관리와 지식 그래프 유지 및 업데이트",
        "role": "로컬 지식 관리 에이전트",
        "workspace_paths": ["."],
        "inputs": ["사용자 요청"],
        "outputs": ["갱신된 지식 DB", "검증된 지식 그래프"],
        "verification": ["변경 파일과 그래프 연결을 확인한다"],
        "constraints": ["근거 없이 지식을 만들지 않는다"],
        "operating_rules": ["지식은 압축적으로 관리한다"],
        "memory_rules": ["장기 맥락만 .claude/memory/에 남긴다"],
        "initial_notes": ["GitHub 템플릿 문구를 남기지 않는다"],
        "bash": {"allow": ["rg *", "sed *"], "deny": ["rm *"]},
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

    def test_project_setup_rewrites_entry_files_without_template_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / "AGENTS.md").write_text("reusable template fork project-neutral\n", encoding="utf-8")
            (root / ".claude/CLAUDE.md").write_text("템플릿 포크 프로젝트-중립\n", encoding="utf-8")

            result = self.run_script(root, project_setup_payload(), "--project-setup", "--update-policy")

            self.assertEqual(result.returncode, 0, result.stderr)
            agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
            claude_text = (root / ".claude/CLAUDE.md").read_text(encoding="utf-8")
            combined = agents_text + "\n" + claude_text
            for expected in (
                "knowledge-base-manager",
                "지식 DB 관리",
                "로컬 지식 관리 에이전트",
            ):
                self.assertIn(expected, combined)
            for forbidden in ("template", "project-neutral", "fork", "템플릿", "프로젝트-중립", "포크"):
                self.assertNotIn(forbidden, combined)
            self.assertFalse((root / ".context/agents/knowledge-base-manager").exists())

            # Generated AGENTS.md must carry the Tasks -> Skills -> agents relationship.
            self.assertIn("Tasks → Skills → Agents", agents_text)
            self.assertIn("가장 작은 작업 단위", agents_text)
            self.assertIn("포괄 이름으로", agents_text)

            # Generated AGENTS.md keeps the full component contract.
            self.assertIn("`.claude/policies/`", agents_text)
            self.assertIn("`.claude/agents/`", agents_text)
            self.assertIn("`.claude/hooks/`", agents_text)

            # Generated CLAUDE.md carries operating principle and component-handling gates.
            self.assertIn("운영 원칙", claude_text)
            self.assertIn("컴포넌트 관리", claude_text)

            # Generated files declare the enforced promotion loop.
            self.assertIn("promotion.json", agents_text)
            self.assertIn("detect_promotions", agents_text)
            self.assertIn("task_ledger", agents_text)
            self.assertIn("promotion.json", claude_text)
            self.assertIn("detect_promotions", claude_text)

            policy = json.loads((root / ".claude/policies/agent-workspace.json").read_text(encoding="utf-8"))
            self.assertEqual(policy["defaults"]["allow"], ["."])
            self.assertEqual(policy["defaults"]["bash"]["allow"], ["rg *", "sed *"])

    def test_project_setup_writes_normalized_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()

            result = self.run_script(root, project_setup_payload(), "--project-setup")

            self.assertEqual(result.returncode, 0, result.stderr)
            input_path = root / "agent-setup.json"
            self.assertTrue(input_path.exists())
            self.assertIn("agent-setup.json", result.stdout)
            saved = json.loads(input_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["agent_name"], "knowledge-base-manager")
            self.assertEqual(saved["workspace_paths"], ["."])
            self.assertEqual(saved["bash"]["allow"], ["rg *", "sed *"])
            self.assertNotIn("denied_paths", saved)

    def test_project_setup_no_save_input_skips_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()

            result = self.run_script(root, project_setup_payload(), "--project-setup", "--no-save-input")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / "agent-setup.json").exists())
            self.assertTrue((root / "AGENTS.md").exists())

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

    def test_skill_document_routes_project_adaptation_to_project_setup_mode(self) -> None:
        text = (REPO_ROOT / ".claude/skills/agent-clone-setup/SKILL.md").read_text(encoding="utf-8")

        self.assertIn("초기 전환", text)
        self.assertIn("프로젝트 자체", text)
        self.assertIn("--project-setup", text)
        self.assertIn("AGENTS.md", text)
        self.assertIn(".claude/CLAUDE.md", text)


if __name__ == "__main__":
    unittest.main()
