#!/usr/bin/env python3
"""Tests for team goals. CI-safe: pure filesystem, no agents/osascript."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPTS_DIR = REPO_ROOT / ".claude/skills/set-team-goal/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import team_goal as tg  # noqa: E402


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.store = Path(self._tmp.name) / ".team"

    def tearDown(self):
        self._tmp.cleanup()

    def make(self, title="연구 목표"):
        return tg.set_goal(
            self.store,
            title=title,
            objective="UMC 분석 결과를 논문 한 편으로 완성",
            deliverable="투고 가능한 논문 초고 1편",
            success_criteria=["전 섹션 초고 완성", "검증 통과"],
            verification=["지도교수 리뷰 통과"],
            scope="UMC 데이터에 한정",
            constraints=["6월 말까지"],
            by="orchestrator",
            clock=lambda: 100,
        )


class SetGoalTests(_Case):
    def test_set_creates_record_with_contract(self):
        rec = self.make()
        self.assertEqual(rec["id"], tg.slugify("연구 목표"))
        self.assertEqual(rec["objective"], "UMC 분석 결과를 논문 한 편으로 완성")
        self.assertEqual(rec["success_criteria"], ["전 섹션 초고 완성", "검증 통과"])
        self.assertEqual(rec["status"], "active")
        self.assertEqual(rec["created_by"], "orchestrator")
        self.assertTrue(tg.goal_path(self.store, rec["id"]).exists())

    def test_missing_contract_element_rejected(self):
        with self.assertRaises(tg.GoalError):
            tg.set_goal(
                self.store, title="x", objective="o", deliverable="d",
                success_criteria=[], verification=["v"],
            )

    def test_missing_verification_rejected(self):
        with self.assertRaises(tg.GoalError):
            tg.set_goal(
                self.store, title="x", objective="o", deliverable="d",
                success_criteria=["s"], verification=[],
            )

    def test_reset_preserves_creation_metadata(self):
        first = self.make()
        second = tg.set_goal(
            self.store, title="연구 목표", objective="갱신된 목표", deliverable="d2",
            success_criteria=["s"], verification=["v"], by="worker-1", clock=lambda: 200,
        )
        self.assertEqual(second["created_by"], "orchestrator")   # preserved
        self.assertEqual(second["created_ts_ns"], 100)            # preserved
        self.assertEqual(second["updated_by"], "worker-1")
        self.assertEqual(second["updated_ts_ns"], 200)
        self.assertEqual(second["objective"], "갱신된 목표")


class StatusTests(_Case):
    def test_status_update(self):
        rec = self.make()
        updated = tg.set_status(self.store, rec["id"], "done", by="worker-1", clock=lambda: 300)
        self.assertEqual(updated["status"], "done")
        self.assertEqual(updated["updated_by"], "worker-1")
        # creation fields preserved
        self.assertEqual(updated["created_by"], "orchestrator")

    def test_status_unknown_goal_errors(self):
        with self.assertRaises(tg.GoalError):
            tg.set_status(self.store, "nope", "done")


class ListShowTests(_Case):
    def test_list_and_filter(self):
        self.make("목표 A")
        b = self.make("목표 B")
        tg.set_status(self.store, b["id"], "done")
        self.assertEqual(len(tg.list_goals(self.store)), 2)
        active = tg.list_goals(self.store, status="active")
        self.assertEqual([g["title"] for g in active], ["목표 A"])

    def test_show(self):
        rec = self.make()
        self.assertEqual(tg.show_goal(self.store, rec["id"])["title"], "연구 목표")

    def test_show_unknown_errors(self):
        with self.assertRaises(tg.GoalError):
            tg.show_goal(self.store, "nope")

    def test_empty_store_lists_nothing(self):
        self.assertEqual(tg.list_goals(self.store), [])


class CliTests(_Case):
    def test_cli_set_and_list(self):
        rc = tg.main([
            "--store", str(self.store), "--by", "orchestrator", "set",
            "--title", "목표 X", "--objective", "o", "--deliverable", "d",
            "--success-criteria", "s1", "--verification", "v1",
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(len(tg.list_goals(self.store)), 1)

    def test_cli_missing_field_returns_1(self):
        rc = tg.main([
            "--store", str(self.store), "set",
            "--title", "y", "--objective", "o", "--deliverable", "d",
            "--verification", "v1",   # no success-criteria
        ])
        self.assertEqual(rc, 1)


class DecomposeTests(_Case):
    def setUp(self):
        super().setUp()
        self.goal = self.make()  # success_criteria = ["전 섹션 초고 완성", "검증 통과"]

    def test_decompose_links_goal_criterion_assignee(self):
        rec = tg.decompose(
            self.store, self.goal["id"], title="섹션 초고 쓰기",
            criterion="전 섹션 초고 완성", assignee="worker-1", by="orchestrator",
        )
        self.assertEqual(rec["goal"], self.goal["id"])
        self.assertEqual(rec["criterion"], "전 섹션 초고 완성")
        self.assertEqual(rec["assignee"], "worker-1")
        self.assertEqual(rec["status"], "pending")
        self.assertTrue(tg.task_path(self.store, self.goal["id"], tg.slugify("섹션 초고 쓰기")).exists())

    def test_decompose_unknown_goal_errors(self):
        with self.assertRaises(tg.GoalError):
            tg.decompose(self.store, "no-such-goal", title="x")

    def test_list_tasks_filters_by_goal(self):
        tg.decompose(self.store, self.goal["id"], title="t1")
        other = tg.set_goal(
            self.store, title="다른 목표", objective="o", deliverable="d",
            success_criteria=["s"], verification=["v"],
        )
        tg.decompose(self.store, other["id"], title="t2")
        self.assertEqual(len(tg.list_tasks(self.store)), 2)
        self.assertEqual(len(tg.list_tasks(self.store, goal_id=self.goal["id"])), 1)

    def test_task_status_update(self):
        tg.decompose(self.store, self.goal["id"], title="섹션 초고 쓰기")
        rec = tg.set_task_status(self.store, self.goal["id"], tg.slugify("섹션 초고 쓰기"), "done", by="worker-1")
        self.assertEqual(rec["status"], "done")

    def test_goal_progress_stop_condition(self):
        gid = self.goal["id"]
        tg.decompose(self.store, gid, title="초고", criterion="전 섹션 초고 완성")
        tg.decompose(self.store, gid, title="검증", criterion="검증 통과")
        # nothing done yet
        self.assertFalse(tg.goal_progress(self.store, gid)["complete"])
        tg.set_task_status(self.store, gid, tg.slugify("초고"), "done")
        self.assertFalse(tg.goal_progress(self.store, gid)["complete"])  # one criterion left
        tg.set_task_status(self.store, gid, tg.slugify("검증"), "done")
        prog = tg.goal_progress(self.store, gid)
        self.assertTrue(prog["complete"])  # all criteria covered by a done task
        self.assertEqual(prog["tasks_done"], 2)

    def test_cli_decompose_and_progress(self):
        rc = tg.main(["--store", str(self.store), "--by", "orchestrator", "decompose",
                      "--id", self.goal["id"], "--task", "초안", "--criterion", "전 섹션 초고 완성", "--assign", "worker-1"])
        self.assertEqual(rc, 0)
        rc2 = tg.main(["--store", str(self.store), "progress", "--id", self.goal["id"]])
        self.assertEqual(rc2, 0)


if __name__ == "__main__":
    unittest.main()
