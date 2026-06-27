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


def test_snapshot_excludes_consumed_for_perf():
    # read_snapshot은 consumed를 안 읽는다(매 3초 refresh 경량화 — 먹통 방지). 살아있는
    # 작업(미claim·claimed)만 스냅샷에 담긴다. consumed 이력은 load_inbox로 따로 조회.
    with TemporaryDirectory() as d:
        root = Path(d)
        _seed(root)
        snap = store.read_snapshot(root)
        assert len(snap.inbox) == 1  # 미claim 1건만(consumed m0 제외)
        assert snap.inbox[0].id == "m1" and snap.inbox[0].state == "unclaimed"
        # 워커 배지 = 자기 팀의 미claim 수
        assert snap.unread_count_for("bob") == 1
        assert snap.unread_count_for("core") == 1


def test_load_inbox_includes_consumed_when_asked():
    # consumed 이력이 필요하면 명시 호출로 읽을 수 있다(타임라인 --all 등).
    with TemporaryDirectory() as d:
        root = Path(d)
        _seed(root)
        msgs = store.load_inbox(root, include_consumed=True)
        states = {m.id: m.state for m in msgs}
        assert states.get("m1") == "unclaimed" and states.get("m0") == "consumed"
        # newest first
        assert msgs[0].ts_ns >= msgs[-1].ts_ns


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
