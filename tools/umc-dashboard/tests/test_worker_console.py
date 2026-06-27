"""WorkerConsole 워커별 버퍼 분리 테스트. Textual 런타임 미기동(버퍼 로직만 검증).

2026-06-27 동시 지시: 여러 워커가 동시에 가동될 수 있어 로그를 워커별 버퍼에 쌓고
선택된 워커 것만 그린다. 여기서는 _repaint(화면 그리기)를 무력화하고 버퍼 상태만 본다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from widgets.worker_console import WorkerConsole  # noqa: E402
from worker_session import WorkerEvent  # noqa: E402


def _console():
    # Textual 위젯 __init__(부모 mount) 우회 — 버퍼 필드만 세팅하고 _repaint는 무력화.
    c = WorkerConsole.__new__(WorkerConsole)
    c._shown = None
    c._buffers = {}
    c._active = set()
    c._repaint = lambda: None        # 화면 그리기 무력화
    c._render_title = lambda: None
    return c


def test_buffers_are_per_worker():
    c = _console()
    c.add_prompt("data-lead", "A 지시")
    c.append_event("data-lead", WorkerEvent("assistant", "A 응답"))
    c.add_prompt("write-lead", "B 지시")
    c.append_event("write-lead", WorkerEvent("assistant", "B 응답"))
    # 두 워커 버퍼가 분리되어 서로 안 섞임
    assert any("A 지시" in ln for ln in c._buffers["data-lead"])
    assert any("A 응답" in ln for ln in c._buffers["data-lead"])
    assert not any("B" in ln for ln in c._buffers["data-lead"])
    assert any("B 지시" in ln for ln in c._buffers["write-lead"])
    assert not any("A" in ln for ln in c._buffers["write-lead"])


def test_active_set_tracks_running_workers():
    c = _console()
    c.set_active("data-lead", True)
    c.set_active("write-lead", True)
    assert c._active == {"data-lead", "write-lead"}
    c.set_active("data-lead", False)
    assert c._active == {"write-lead"}


def test_focus_switches_shown_worker():
    c = _console()
    c.add_prompt("data-lead", "A")
    c.add_prompt("write-lead", "B")
    c.focus_worker("write-lead")
    assert c._shown == "write-lead"
    c.focus_worker("data-lead")
    assert c._shown == "data-lead"


def test_first_prompt_auto_shows_that_worker():
    c = _console()
    assert c._shown is None
    c.add_prompt("scout-lead", "검색해")
    assert c._shown == "scout-lead"  # 첫 지시 워커가 자동 표시


def test_trim_caps_buffer_length():
    c = _console()
    for i in range(WorkerConsole.MAX_LINES + 50):
        c.append_event("data-lead", WorkerEvent("assistant", f"line {i}"))
    assert len(c._buffers["data-lead"]) == WorkerConsole.MAX_LINES  # 오래된 건 잘림


def test_empty_event_text_skipped():
    c = _console()
    c.append_event("data-lead", WorkerEvent("assistant", "   "))
    assert c._buffers.get("data-lead", []) == []


def test_append_throttles_repaint():
    # 대량 append가 즉시 _repaint를 부르지 않고 _dirty만 세운다(렌더 폭주 방지).
    c = _console()
    c._dirty = False
    repaints = []
    c._repaint = lambda: repaints.append(1)
    c._shown = "data-engineer"
    for i in range(100):
        c.append_event("data-engineer", WorkerEvent("assistant", f"line {i}"))
    assert repaints == []          # 즉시 그리지 않음
    assert c._dirty is True        # dirty만 세움
    # flush_tick 한 번 = 한 번만 그림
    c._flush_tick()
    assert len(repaints) == 1
    assert c._dirty is False
    # dirty 아니면 flush는 no-op
    c._flush_tick()
    assert len(repaints) == 1


def test_hidden_worker_does_not_mark_dirty():
    # 안 보이는 워커의 이벤트는 dirty조차 안 세운다(보이는 워커만 그릴 가치).
    c = _console()
    c._dirty = False
    c._shown = "data-engineer"
    c.append_event("other-worker", WorkerEvent("assistant", "x"))
    assert c._dirty is False
    assert any("x" in ln for ln in c._buffers["other-worker"])  # 버퍼엔 쌓임
