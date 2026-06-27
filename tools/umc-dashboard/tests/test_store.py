"""store.py 파싱 테스트 — 임시 .project/ 트리, 실 store 미접촉. CI-safe."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import store  # noqa: E402


def _seed(root: Path) -> None:
    """팀 전용 메일박스 모델: 메일박스는 teams/<팀>/.claude/inbox/."""
    team = root / ".project"
    (team / "goals").mkdir(parents=True)
    (root / "AGENTS.md").write_text("x")
    team.joinpath("team.json").write_text(json.dumps({
        "members": ["alice", "bob"],
        "roles": {"alice": "리드 역할", "bob": "워커 역할"},
        "subteams": [{"name": "core", "members": ["alice", "bob"], "orchestrator": "alice",
                      "reminders_list": "umc"}],
    }))
    core_box = root / "teams" / "core" / ".claude" / "inbox"
    (core_box / ".consumed").mkdir(parents=True)
    # unclaimed message in core team mailbox
    (core_box / "m1.json").write_text(json.dumps({
        "id": "m1", "from": "alice", "to_team": "core", "recipients": ["alice", "bob"],
        "claimed_by": None, "subject": "작업 위임", "body": "...", "ts_ns": 200}))
    # consumed message in core team mailbox
    (core_box / ".consumed" / "m0.json").write_text(json.dumps({
        "id": "m0", "from": "bob", "to_team": "core", "subject": "회신", "body": "...", "ts_ns": 100}))
    (team / "goals" / "g.json").write_text(json.dumps({
        "id": "g", "title": "목표A", "objective": "obj", "success_criteria": ["c1", "c2"], "status": "active"}))


def test_roster_and_subteams():
    with TemporaryDirectory() as d:
        root = Path(d)
        _seed(root)
        snap = store.read_snapshot(root)
        assert len(snap.workers) == 2
        alice = next(w for w in snap.workers if w.name == "alice")
        assert alice.team == "core" and alice.is_orchestrator
        assert alice.role == "리드 역할"


def test_inbox_unclaimed_vs_consumed():
    with TemporaryDirectory() as d:
        root = Path(d)
        _seed(root)
        snap = store.read_snapshot(root)
        assert len(snap.inbox) == 2  # 1 unclaimed + 1 consumed in core mailbox
        # 워커 배지 = 자기 팀의 미claim 수. alice·bob 둘 다 core 팀 → 1
        assert snap.unread_count_for("bob") == 1
        assert snap.unread_count_for("alice") == 1
        # 팀명으로도 조회 가능
        assert snap.unread_count_for("core") == 1
        # newest first
        assert snap.inbox[0].ts_ns >= snap.inbox[1].ts_ns
        # state 태깅
        states = {m.id: m.state for m in snap.inbox}
        assert states["m1"] == "unclaimed" and states["m0"] == "consumed"


def test_goals():
    with TemporaryDirectory() as d:
        root = Path(d)
        _seed(root)
        goals = store.load_goals(root)
        assert len(goals) == 1 and goals[0].title == "목표A"
        assert len(goals[0].success_criteria) == 2


def test_candidates_bucket_shape():
    with TemporaryDirectory() as d:
        root = Path(d)
        _seed(root)
        cdir = root / ".context" / "promotions"
        cdir.mkdir(parents=True)
        (cdir / "candidates.json").write_text(json.dumps({
            "agent": [{"kind": "agent", "key": "a+b", "cousage": 2, "distinct_sessions": 1,
                       "skills": ["a", "b"]}],
            "skill": [],
        }))
        cands = store.load_candidates(root)
        assert len(cands) == 1
        assert cands[0].kind == "agent" and "co-used 2x" in cands[0].detail


def test_malformed_file_does_not_crash():
    with TemporaryDirectory() as d:
        root = Path(d)
        _seed(root)
        # half-written tmp file mid atomic-rename, in the team mailbox
        (root / "teams" / "core" / ".claude" / "inbox" / "broken.json").write_text("{ not json")
        snap = store.read_snapshot(root)  # must not raise
        assert snap.unread_count_for("core") == 1  # broken one skipped
