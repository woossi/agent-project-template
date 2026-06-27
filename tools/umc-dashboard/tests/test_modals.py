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


def test_base_button_pressed_stops_event():
    """ok/cancel 버튼 핸들러가 e.stop()으로 버블링을 끊는지(중복 처리 예방)."""
    class FakeButton:
        id = "ok"

    class FakeEvent:
        def __init__(self):
            self.button = FakeButton()
            self.stopped = 0
        def stop(self):
            self.stopped += 1

    p = _Probe(is_current=True)
    submitted = []
    p.action_submit = lambda: submitted.append(True)
    e = FakeEvent()
    _BaseModal.on_button_pressed(p, e)
    assert e.stopped == 1  # 이벤트 전파 차단
    assert submitted == [True]  # ok → submit
