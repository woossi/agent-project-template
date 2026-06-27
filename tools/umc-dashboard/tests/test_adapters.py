"""adapters.py 테스트 — 가짜 runner 주입, 실제 CLI/미리알림 미실행. CI-safe."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import TeamCli  # noqa: E402


class FakeRunner:
    """argv를 기록하고 미리 지정한 (rc, stdout, stderr)를 돌려준다."""
    def __init__(self, rc=0, stdout="", stderr=""):
        self.calls: list[list[str]] = []
        self.rc, self.stdout, self.stderr = rc, stdout, stderr

    def __call__(self, argv, cwd):
        self.calls.append(list(argv))
        return self.rc, self.stdout, self.stderr


def test_reminders_pull_parses_envelope():
    fake = FakeRunner(stdout=json.dumps({"ok": True, "op": "pull",
                                         "result": [{"id": "x", "name": "T", "completed": False}]}))
    cli = TeamCli(Path("/repo"), runner=fake)
    res = cli.reminders_pull("umc")
    assert res.ok and res.data[0]["name"] == "T"
    # 올바른 스크립트·서브커맨드로 호출됐는지
    argv = fake.calls[0]
    assert "reminders_bridge.py" in argv[1] and "pull" in argv and "umc" in argv


def test_reminders_add_builds_flags():
    fake = FakeRunner(stdout=json.dumps({"ok": True, "result": {"id": "n"}}))
    cli = TeamCli(Path("/repo"), runner=fake)
    cli.reminders_add("umc", "새 작업", notes="메모", priority=5, due="2026-06-30")
    argv = fake.calls[0]
    assert "add" in argv and "새 작업" in argv
    assert "--notes" in argv and "--priority" in argv and "5" in argv and "--due" in argv


def test_inbox_post_fans_out_recipients():
    fake = FakeRunner(stdout=json.dumps({"ok": True, "result": {"posted": 2}}))
    cli = TeamCli(Path("/repo"), runner=fake)
    cli.inbox_post("orchestrator", ["alice", "bob"], "제목", "본문")
    argv = fake.calls[0]
    assert argv.count("--to") == 2 and "alice" in argv and "bob" in argv
    assert "--as" in argv and "orchestrator" in argv


def test_resolve_promotion_argv():
    fake = FakeRunner(stdout=json.dumps({"ok": True}))
    cli = TeamCli(Path("/repo"), runner=fake)
    cli.resolve_promotion("agent", "a+b", "decline", reason="중복")
    argv = fake.calls[0]
    assert "detect_promotions.py" in argv[1]
    assert argv[2] == "resolve" and "--kind" in argv and "agent" in argv
    assert "--decision" in argv and "decline" in argv and "--reason" in argv


def test_non_json_output_is_handled():
    fake = FakeRunner(rc=1, stdout="boom", stderr="권한 없음")
    cli = TeamCli(Path("/repo"), runner=fake)
    res = cli.reminders_list_teams()
    assert not res.ok and "권한" in res.error


def test_error_envelope_surfaces_message():
    fake = FakeRunner(stdout=json.dumps({"ok": False, "error": "list not found"}))
    cli = TeamCli(Path("/repo"), runner=fake)
    res = cli.reminders_pull("nope")
    assert not res.ok and res.error == "list not found"
