"""SessionPool 테스트 — 가짜 WorkerSession 주입, 실 subprocess 미실행."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from session_pool import SessionPool  # noqa: E402
from worker_session import WorkerEvent, TurnResult  # noqa: E402


class FakeSession:
    """WorkerSession 인터페이스를 흉내 — send마다 이벤트를 흘리고 sid를 잡는다."""

    def __init__(self, worker, team, root, *, permission_mode="acceptEdits"):
        self.worker = worker
        self.team = team
        self.session_id = ""
        self.sent: list[str] = []

    def send(self, prompt, *, on_event=None, timeout=None):
        self.sent.append(prompt)
        self.session_id = f"sid-{self.worker}"
        evs = [WorkerEvent("system", f"세션 시작 {self.session_id}"),
               WorkerEvent("assistant", f"응답: {prompt[:10]}"),
               WorkerEvent("result", "완료(success)")]
        for e in evs:
            if on_event:
                on_event(e)
        return TurnResult(True, session_id=self.session_id,
                          text=f"응답: {prompt[:10]}", events=evs)


def _pool(tmp_path):
    return SessionPool(tmp_path, session_factory=FakeSession)


def test_session_reuse_same_worker():
    pool = _pool(Path("/tmp"))
    s1 = pool.session("paper-scout", "scout")
    s2 = pool.session("paper-scout", "scout")
    assert s1 is s2  # 같은 워커 → 같은 세션(멀티턴 컨텍스트 유지)


def test_has_session_after_send():
    pool = _pool(Path("/tmp"))
    assert pool.has_session("paper-scout") is False
    pool.send("paper-scout", "scout", "안녕")
    assert pool.has_session("paper-scout") is True
    assert "paper-scout" in pool.active_workers()


def test_events_streamed_to_callback():
    pool = _pool(Path("/tmp"))
    got: list[WorkerEvent] = []
    r = pool.send("data-engineer", "data", "데이터 정리해", on_event=got.append)
    assert r.ok
    kinds = [e.kind for e in got]
    assert kinds == ["system", "assistant", "result"]
    assert any("응답" in e.text for e in got)


def test_reset_starts_new_conversation():
    pool = _pool(Path("/tmp"))
    pool.send("paper-scout", "scout", "첫 턴")
    assert pool.has_session("paper-scout")
    pool.reset("paper-scout")
    assert pool.has_session("paper-scout") is False
    assert "paper-scout" not in pool.active_workers()
