"""개별 지시(c) 역할 게이트 테스트 — 팀장만 직접 지시 가능, 워커는 차단.

계층 거버넌스(2026-06-27): GUI의 'c 개별 지시'는 팀장(lead)에게만 보낸다. 워커가
선택되면 action_instruct가 차단하고 그 팀장을 안내한다. 여기서는 게이트의 판정
헬퍼(_is_lead/_team_lead)와 action_instruct의 워커-차단 분기를 검증한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import store  # noqa: E402
from app import Dashboard  # noqa: E402


def _snapshot():
    """data 팀(팀장 data-lead + 워커 2명), write 팀(팀장 write-lead) 스냅샷."""
    workers = [
        store.Worker(name="data-lead", role="lead", team="data", is_orchestrator=True),
        store.Worker(name="data-engineer", role="eng", team="data", is_orchestrator=False),
        store.Worker(name="data-curator", role="cur", team="data", is_orchestrator=False),
        store.Worker(name="write-lead", role="lead", team="write", is_orchestrator=True),
    ]
    subteams = [
        store.Subteam(name="data", members=["data-lead", "data-engineer", "data-curator"],
                      orchestrator="data-lead"),
        store.Subteam(name="write", members=["write-lead"], orchestrator="write-lead"),
    ]
    return store.Snapshot(workers=workers, subteams=subteams)


def _dash():
    """Dashboard를 __init__ 부작용 없이 만들어 _snap만 주입(헬퍼 단위 테스트용)."""
    d = Dashboard.__new__(Dashboard)
    d._snap = _snapshot()
    return d


def test_is_lead_distinguishes_lead_from_worker():
    d = _dash()
    assert d._is_lead("data-lead") is True
    assert d._is_lead("write-lead") is True
    assert d._is_lead("data-engineer") is False
    assert d._is_lead("data-curator") is False
    assert d._is_lead("nobody") is False  # 미등록은 팀장 아님


def test_team_lead_resolves_orchestrator():
    d = _dash()
    assert d._team_lead("data") == "data-lead"
    assert d._team_lead("write") == "write-lead"
    assert d._team_lead("nonexistent") is None


def test_action_instruct_blocks_worker(monkeypatch):
    """워커 선택 시 action_instruct가 차단 토스트를 내고 모달을 push하지 않는다."""
    d = _dash()
    monkeypatch.setattr(d, "_selected_worker", lambda: ("data-engineer", "data"))
    toasts, pushed = [], []
    monkeypatch.setattr(d, "_toast", lambda ok, msg: toasts.append((ok, msg)))
    monkeypatch.setattr(d, "push_screen", lambda *a, **k: pushed.append(a))

    d.action_instruct()

    assert pushed == []  # 모달 안 뜸 — 지시 경로 차단
    assert toasts and toasts[-1][0] is False
    assert "직접 지시 불가" in toasts[-1][1]
    assert "data-lead" in toasts[-1][1]  # 팀장 안내 포함


def test_action_instruct_allows_lead(monkeypatch):
    """팀장 선택 시 게이트를 통과해 InstructModal을 push한다."""
    d = _dash()
    monkeypatch.setattr(d, "_selected_worker", lambda: ("data-lead", "data"))
    d._instructing = set()
    d.pool = type("P", (), {"has_session": lambda self, w: False})()
    pushed = []
    monkeypatch.setattr(d, "_toast", lambda ok, msg: None)
    monkeypatch.setattr(d, "push_screen", lambda *a, **k: pushed.append(a))
    monkeypatch.setattr(d, "query_one", lambda *a, **k: type(
        "C", (), {"focus_worker": lambda self, w: None})())

    d.action_instruct()

    assert len(pushed) == 1  # InstructModal이 떴다 — 팀장은 지시 가능
