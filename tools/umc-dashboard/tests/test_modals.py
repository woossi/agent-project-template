"""modals.py 회귀 테스트 — _close 재진입/활성 가드. CI-safe: Textual 런타임 미기동.

배경(2026-06-27 버그): InstructModal에서 [취소]/빈입력 [지시] 시 _close→dismiss가
두 번 불려 ScreenStackError("Can't pop screen; ...")가 났다. 버튼 Pressed와 키 바인딩이
같은 턴에 겹쳐 dismiss가 빈 스택을 또 pop한 것. 가드 2겹으로 막는다:
  1) _closed 플래그 — 모달당 _close 1회만 효력
  2) is_current 체크 — 스택 맨 위(활성)일 때만 dismiss
여기서는 dismiss/is_current/_on_submit를 가짜로 두고 가드 로직만 검증한다(런타임 불요).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from widgets.modals import _BaseModal  # noqa: E402


class _Probe(_BaseModal):
    """is_current를 주입 가능한 프로브. _close 가드만 검사한다."""
    def __init__(self, is_current: bool):
        self._on_submit = lambda p: self._calls.append(p)
        self._closed = False
        self._calls = []
        self._dismissed = 0
        self._cur = is_current

    @property
    def is_current(self) -> bool:
        return self._cur

    def dismiss(self, *a, **k):
        self._dismissed += 1


def test_close_normal_submits_and_dismisses_once():
    p = _Probe(is_current=True)
    p._close({"prompt": "hi"})
    assert p._dismissed == 1
    assert p._calls == [{"prompt": "hi"}]


def test_double_close_is_blocked():
    # 같은 턴에 두 번 _close가 불려도 두 번째는 무효 → ScreenStackError 회피.
    p = _Probe(is_current=True)
    p._close({"prompt": "x"})
    p._close(None)
    assert p._dismissed == 1  # 여전히 1


def test_close_on_inactive_modal_does_not_dismiss():
    # 스택 맨 위가 아니면 dismiss를 호출하지 않는다(방어적).
    p = _Probe(is_current=False)
    p._close(None)
    assert p._dismissed == 0
    assert p._closed is True  # 이후 재호출도 무효 처리됨


def test_cancel_path_dismisses_without_callback():
    p = _Probe(is_current=True)
    p._close(None)  # payload None = 취소
    assert p._dismissed == 1
    assert p._calls == []


class _FakeEvent:
    def __init__(self):
        self.stopped = 0
    def stop(self):
        self.stopped += 1


def test_ok_handler_submits_and_stops():
    # @on(Button.Pressed, "#ok") 핸들러 — submit + e.stop().
    p = _Probe(is_current=True)
    submitted = []
    p.action_submit = lambda: submitted.append(True)
    e = _FakeEvent()
    _BaseModal._on_ok(p, e)
    assert e.stopped == 1 and submitted == [True]


def test_cancel_handler_cancels_and_stops():
    p = _Probe(is_current=True)
    cancelled = []
    p.action_cancel = lambda: cancelled.append(True)
    e = _FakeEvent()
    _BaseModal._on_cancel(p, e)
    assert e.stopped == 1 and cancelled == [True]


def test_no_legacy_on_button_pressed():
    # 회귀 방지: on_button_pressed(이름 기반 핸들러)가 있으면 Textual이 MRO에서
    # _BaseModal·하위 둘 다 호출해 preset 클릭 시 모달이 닫히는 버그가 재발한다.
    # @on 셀렉터 라우팅만 쓰고 on_button_pressed는 절대 정의하지 않는다.
    import widgets.modals as m
    assert not hasattr(m._BaseModal, "on_button_pressed")
    assert not hasattr(m.InstructModal, "on_button_pressed")


def test_preset_prompt_inbox_is_lead_facing():
    # 'inbox' preset은 팀장 전용 — claim해서 팀 보드로 분배·ack(워커는 메일박스 권한 없음).
    from widgets.modals import preset_prompt
    p = preset_prompt("inbox", worker="data-lead", team="data")
    assert "팀장으로서" in p
    assert "read --team data" in p
    assert "claim --team data --as data-lead" in p
    assert "ack --team data" in p
    assert "teams/data/.claude/tasks/tasks.md" in p  # 팀 보드 분배
    assert "write-task" in p


def test_preset_prompt_tasks_is_worker_facing():
    # 'tasks' preset은 워커 전용 — 팀 보드 read·수행·보고, 메일박스 금지.
    from widgets.modals import preset_prompt
    p = preset_prompt("tasks", worker="data-engineer", team="data")
    assert "teams/data/.claude/tasks/tasks.md" in p
    assert "메일박스는 보지 마라" in p
    assert "post --to-team data" in p  # 팀장에게 보고
    assert "data-engineer" in p


def test_preset_prompt_reminders():
    from widgets.modals import preset_prompt
    p = preset_prompt("reminders", worker="x", team="scout")
    assert "umc-scout" in p and "pull" in p


def test_preset_prompt_unknown_key_empty():
    from widgets.modals import preset_prompt
    assert preset_prompt("nope", worker="x", team="data") == ""
