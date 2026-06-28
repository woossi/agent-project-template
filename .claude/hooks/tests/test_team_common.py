#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".claude/lib"))

from team_common.candidate_store import decision_record_path, load_decisions, write_team_shard  # noqa: E402
from team_common.paths import find_team_root  # noqa: E402
from team_common.roster import TeamIndex, discover_worker_dirs  # noqa: E402


class TeamCommonTests(unittest.TestCase):
    def test_find_team_root_requires_project_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "teams/data/w"
            child.mkdir(parents=True)
            self.assertIsNone(find_team_root(child))
            (root / ".project").mkdir()
            self.assertEqual(find_team_root(child), root.resolve())

    def test_team_index_reads_roster_once_as_explicit_layer(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".project").mkdir()
            (root / ".project/team.json").write_text(json.dumps({
                "members": ["a", "b"],
                "subteams": [{"name": "data", "members": ["a"]}, {"name": "write", "members": ["b"]}],
            }), encoding="utf-8")
            index = TeamIndex.load(root)
            self.assertEqual(index.subteams["data"], ["a"])
            self.assertEqual(index.worker_to_team, {"a": "data", "b": "write"})
            self.assertEqual(index.worker_at(root / "teams/data/a/x.md"), "a")
            self.assertIsNone(index.worker_at(root / "teams/data/fake/x.md"))

    def test_discover_worker_dirs_preserves_team_precedence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "teams/data/w/.context/task-log").mkdir(parents=True)
            (root / "agents/w/.context/task-log").mkdir(parents=True)
            found = discover_worker_dirs(root, lambda p: (p / ".context/task-log").is_dir())
            self.assertEqual(found["w"], root / "teams/data/w")

    def test_decision_paths_include_hash_for_slug_collisions(self) -> None:
        with TemporaryDirectory() as tmp:
            decisions = Path(tmp)
            p1 = decision_record_path(decisions, "memory", "a b")
            p2 = decision_record_path(decisions, "memory", "a-b")
            self.assertNotEqual(p1.name, p2.name)
            self.assertTrue(p1.name.startswith("memory__a_b__"))

    def test_candidate_shard_folds_runner_to_team(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_team_shard(root, ".project/promotions/candidates", {"x": []}, "worker-1")
            self.assertEqual(path, root / ".project/promotions/candidates/team.json")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"x": []})

    def test_load_decisions_is_kind_key_indexed(self) -> None:
        with TemporaryDirectory() as tmp:
            ddir = Path(tmp)
            records = [
                {"kind": "term", "key": "LISA", "decision": "decline"},
                {"kind": "memory", "key": "m", "decision": "promote"},
            ]
            for i, rec in enumerate(records):
                (ddir / f"{i}.json").write_text(json.dumps(rec), encoding="utf-8")
            loaded = load_decisions(ddir, ("term", "memory"))
            self.assertEqual(loaded["term"]["LISA"]["decision"], "decline")
            self.assertEqual(loaded["memory"]["m"]["decision"], "promote")


if __name__ == "__main__":
    unittest.main()

