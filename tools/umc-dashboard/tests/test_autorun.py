"""워커 상시 구동(autorun) 폴링 테스트.

상시 모드가 켜지면 주기마다 일반 워커(팀장 제외)를 'tasks 보드 확인·수행·보고'
preset으로 깨운다. 검증 포인트:
  - OFF면 아무도 안 깨움
  - ON이면 일반 워커만 깨우고 팀장은 제외('팀장과만 소통' 모델)
  - 이미 가동 중(_instructing)인 워커는 건너뜀(중복·토큰폭발 방지)
  - 토글이 상태를 뒤집고 즉시 1회 tick
실제 claude를 띄우지 않도록 _instruct_worker는 mock한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import store  # noqa: E402
import app as app_module  # noqa: E402
from app import Dashboard  # noqa: E402


def _snapshot():
    workers = [
        store.Worker(name="data-lead", role="lead", team="data", is_orchestrator=True),
        store.Worker(name="data-engineer", role="eng", team="data", is_orchestrator=False),
        store.Worker(name="data-curator", role="cur", team="data", is_orchestrator=False),
        store.Worker(name="write-lead", role="lead", team="write", is_orchestrator=True),
        store.Worker(name="manuscript-writer", role="w", team="write", is_orchestrator=False),
    ]
    subteams = [
        store.Subteam(name="data", members=["data-lead", "data-engineer", "data-curator"],
                      orchestrator="data-lead"),
        store.Subteam(name="write", members=["write-lead", "manuscript-writer"],
                      orchestrator="write-lead"),
    ]
    return store.Snapshot(workers=workers, subteams=subteams)


def _dash(monkeypatch):
    """Dashboard를 __init__ 부작용 없이 만들고, 워커 깨움을 가로채는 spy를 단다."""
    d = Dashboard.__new__(Dashboard)
    d._snap = _snapshot()
    d._instructing = set()
    d._autorun_on = False
    d._autorun_seconds = 45.0
    d._autorun_cooldown_seconds = 600.0
    d._autorun_last_wake = {}
    woken = []
    # _instruct_worker는 실제 claude를 띄우므로 spy로 대체(깨운 워커만 기록).
    monkeypatch.setattr(d, "_instruct_worker", lambda w, t, p: woken.append((w, t, p)))
    monkeypatch.setattr(d, "_toast", lambda ok, msg: None)
    monkeypatch.setattr(d, "refresh_data", lambda: None)
    # WorkerConsole 호출(add_prompt/set_active)을 no-op 객체로.
    console = type("C", (), {"add_prompt": lambda *a: None, "set_active": lambda *a: None})()
    monkeypatch.setattr(d, "query_one", lambda *a, **k: console)
    return d, woken


def test_autorun_off_wakes_nobody(monkeypatch):
    d, woken = _dash(monkeypatch)
    d._autorun_on = False
    d._autorun_tick()
    assert woken == []  # OFF면 아무도 안 깨움


def test_autorun_is_not_hardcoded_picks_up_new_worker(monkeypatch):
    """워커 목록은 로스터(snapshot.workers)에서 동적으로 온다 — 하드코딩 아님.
    런타임에 새 워커를 로스터에 추가하면 다음 tick에서 자동으로 깨워져야 한다."""
    d, woken = _dash(monkeypatch)
    d._autorun_on = True
    # 새 팀+워커를 로스터에 추가(team-init이 team.json에 등록하면 일어나는 일).
    d._snap.workers.append(
        store.Worker(name="new-analyst", role="a", team="analysis", is_orchestrator=False))
    d._snap.workers.append(
        store.Worker(name="analysis-lead", role="lead", team="analysis", is_orchestrator=True))
    d._autorun_tick()
    names = {w for w, _, _ in woken}
    assert "new-analyst" in names          # 새 워커 자동 포함
    assert "analysis-lead" not in names    # 새 팀장도 자동 제외
    # 코드에 숫자/이름 하드코딩이 없으므로 로스터 크기와 무관하게 동작.
    assert len(names) == 4  # 기존 워커 3 + 새 워커 1 (로스터가 5→7명으로 늘어도 무관)


def test_autorun_on_wakes_workers_not_leads(monkeypatch):
    d, woken = _dash(monkeypatch)
    d._autorun_on = True
    d._autorun_tick()
    names = {w for w, _, _ in woken}
    assert names == {"data-engineer", "data-curator", "manuscript-writer"}  # 워커만
    assert "data-lead" not in names and "write-lead" not in names  # 팀장 제외


def test_autorun_skips_already_running(monkeypatch):
    d, woken = _dash(monkeypatch)
    d._autorun_on = True
    d._instructing = {"data-engineer"}  # 이미 가동 중
    d._autorun_tick()
    names = {w for w, _, _ in woken}
    assert "data-engineer" not in names  # 중복 안 깨움
    assert names == {"data-curator", "manuscript-writer"}


def test_autorun_cooldown_prevents_immediate_rewake(monkeypatch):
    d, woken = _dash(monkeypatch)
    d._autorun_on = True
    monkeypatch.setattr(app_module.time, "time", lambda: 1000.0)
    d._autorun_tick()
    assert len(woken) == 3
    d._instructing.clear()  # 턴이 끝났더라도 쿨다운 전이면 다시 깨우면 안 됨
    woken.clear()
    monkeypatch.setattr(app_module.time, "time", lambda: 1100.0)
    d._autorun_tick()
    assert woken == []
    monkeypatch.setattr(app_module.time, "time", lambda: 1701.0)
    d._autorun_tick()
    assert len(woken) == 3


def test_autorun_uses_tasks_preset(monkeypatch):
    d, woken = _dash(monkeypatch)
    d._autorun_on = True
    d._autorun_tick()
    # 깨운 prompt가 'tasks' preset(보드 확인·메일박스 금지)인지
    _, _, prompt = woken[0]
    assert "보드" in prompt and "메일박스" in prompt


def test_toggle_flips_and_ticks_immediately(monkeypatch):
    d, woken = _dash(monkeypatch)
    assert d._autorun_on is False
    d.action_toggle_autorun()          # OFF -> ON: 즉시 1회 tick
    assert d._autorun_on is True
    assert len(woken) == 3             # 워커 3명 즉시 깨움
    woken.clear()
    d.action_toggle_autorun()          # ON -> OFF: tick 안 함
    assert d._autorun_on is False
    assert woken == []
