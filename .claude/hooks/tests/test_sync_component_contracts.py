#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / ".claude/hooks/sync_component_contracts.py"


class SyncComponentContractsTest(unittest.TestCase):
    def make_root(self, root: Path) -> None:
        (root / ".claude/skills/write-skill/templates").mkdir(parents=True)
        (root / ".claude/skills/write-task/templates").mkdir(parents=True)
        (root / ".claude/skills/write-subagent/templates").mkdir(parents=True)
        (root / ".claude/agents").mkdir(parents=True)

        (root / ".claude/skills/write-skill/templates/SKILL.md").write_text("# 스킬: example\n", encoding="utf-8")
        (root / ".claude/skills/write-task/templates/task.md").write_text("# 작업\n", encoding="utf-8")
        (root / ".claude/skills/write-subagent/templates/AGENT.md").write_text(
            "---\nname: agent-name\ndescription: Use when needed.\ntools: Read\n---\n\n# Role\n",
            encoding="utf-8",
        )
        (root / ".claude/agents/agents.md").write_text(
            "# Agent Index\n\n## Files\n\n| Path | Role |\n| --- | --- |\n\n## Maintenance\n\n- Keep current.\n",
            encoding="utf-8",
        )
        (root / ".claude/agents/reviewer.md").write_text(
            "---\nname: reviewer\ndescription: Use when reviewing scoped changes.\ntools: Read\n---\n\n# Role\nReview.\n",
            encoding="utf-8",
        )

    def run_hook(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOK), "--project-root", str(root)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_syncs_cross_contract_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_root(root)

            result = self.run_hook(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            skill_template = (root / ".claude/skills/write-skill/templates/SKILL.md").read_text(encoding="utf-8")
            task_template = (root / ".claude/skills/write-task/templates/task.md").read_text(encoding="utf-8")
            agent_template = (root / ".claude/skills/write-subagent/templates/AGENT.md").read_text(encoding="utf-8")
            agent_index = (root / ".claude/agents/agents.md").read_text(encoding="utf-8")

            self.assertIn("## 계약 연계", skill_template)
            self.assertIn("작업은 이 스킬을 `사용할 스킬` 입력으로 참조한다", skill_template)
            self.assertIn("서브에이전트", task_template)
            self.assertIn("스킬 능력", agent_template)
            self.assertNotIn("`.claude/agents/reviewer.md`", agent_index)

            # Tasks -> Skills -> agents relationship must be encoded in each section.
            self.assertIn("반복되는 작업", skill_template)
            self.assertIn("포괄 이름으로 승격", skill_template)
            self.assertIn("가장 작은 작업 단위", task_template)
            self.assertIn("자동으로 기록", task_template)
            self.assertIn("진행 로그", task_template)
            self.assertIn("특정 스킬 패키지", agent_template)
            self.assertIn("독립 컨텍스트", agent_template)
            self.assertIn("참조하여", agent_template)

            before = {
                path: path.read_text(encoding="utf-8")
                for path in [
                    root / ".claude/skills/write-skill/templates/SKILL.md",
                    root / ".claude/skills/write-task/templates/task.md",
                    root / ".claude/skills/write-subagent/templates/AGENT.md",
                ]
            }
            second = self.run_hook(root)
            self.assertEqual(second.returncode, 0, second.stderr)
            after = {path: path.read_text(encoding="utf-8") for path in before}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
