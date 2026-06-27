"""중앙 하단(우): 워커별 headless 대화 콘솔 (워커별 버퍼 분리).

tmux 창을 들여다보던 것을 대체한다. 여러 워커가 동시에 headless로 가동될 수 있으므로
(2026-06-27 동시 지시 허용), 로그를 워커별 버퍼에 따로 쌓고 현재 선택된 워커의 로그만
표시한다. app이 이벤트 도착마다 append_event(worker, ev)를 호출한다(워커 스레드 →
call_from_thread). 사이드바에서 워커를 바꾸면 그 워커의 버퍼로 화면을 전환한다.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from worker_session import WorkerEvent

_ICON = {
    "system": "[dim]▶[/dim]",
    "assistant": "[green]💬[/green]",
    "tool_use": "[yellow]⚙[/yellow]",
    "result": "[blue]✓[/blue]",
    "error": "[red]✗[/red]",
    "raw": "[dim]·[/dim]",
}

_EMPTY = "[dim]워커를 선택하고 'c'로 지시하세요[/dim]"


class WorkerConsole(VerticalScroll):
    """워커별 대화 로그. 동시 가동을 지원하되 화면엔 선택 워커 것만 그린다."""

    MAX_LINES = 400

    def __init__(self, **kw):
        super().__init__(**kw)
        self._shown: str | None = None              # 현재 화면에 표시 중인 워커
        self._buffers: dict[str, list[str]] = {}    # 워커별 로그 버퍼
        self._active: set[str] = set()              # 가동 중(턴 진행 중)인 워커

    def compose(self) -> ComposeResult:
        yield Static("워커 콘솔", classes="panel-title", id="console-title")
        yield Static(_EMPTY, id="console-body")

    def _buf(self, worker: str) -> list[str]:
        return self._buffers.setdefault(worker, [])

    def focus_worker(self, worker: str | None) -> None:
        """표시 대상 워커를 바꾼다. 그 워커의 버퍼로 화면을 다시 그린다."""
        self._shown = worker
        self._repaint()

    def set_active(self, worker: str, active: bool) -> None:
        """가동 상태 토글 — 타이틀에 ● 표시로 어떤 워커가 도는지 보인다."""
        if active:
            self._active.add(worker)
        else:
            self._active.discard(worker)
        self._render_title()

    # 이벤트는 항상 worker를 동반한다 — 어느 워커 버퍼에 쌓을지 명시.
    def add_prompt(self, worker: str, prompt: str) -> None:
        buf = self._buf(worker)
        buf.append(f"\n[b on grey23] ▶ {worker} 에게 지시 [/]")
        buf.append(f"[white]{prompt}[/white]")
        self._trim(worker)
        if self._shown is None:
            self._shown = worker
        if worker == self._shown:
            self._repaint()

    def append_event(self, worker: str, ev: WorkerEvent) -> None:
        text = ev.text.strip()
        if not text:
            return
        self._buf(worker).append(f"{_ICON.get(ev.kind, '·')} {text}")
        self._trim(worker)
        if worker == self._shown:
            self._repaint()

    def add_status(self, worker: str, msg: str, *, ok: bool = True) -> None:
        mark = "[blue]✓[/blue]" if ok else "[red]✗[/red]"
        self._buf(worker).append(f"{mark} [dim]{msg}[/dim]")
        self._trim(worker)
        if worker == self._shown:
            self._repaint()

    def _trim(self, worker: str) -> None:
        buf = self._buffers.get(worker)
        if buf and len(buf) > self.MAX_LINES:
            self._buffers[worker] = buf[-self.MAX_LINES:]

    def _render_title(self) -> None:
        title = "워커 콘솔"
        if self._shown:
            running = " [yellow]●가동중[/yellow]" if self._shown in self._active else ""
            others = sorted(self._active - {self._shown})
            extra = f"  [dim](+{len(others)} 동시가동: {', '.join(others)})[/dim]" if others else ""
            title = f"워커 콘솔 — [b]{self._shown}[/b]{running}{extra}"
        try:
            self.query_one("#console-title", Static).update(title)
        except Exception:
            pass

    def _repaint(self) -> None:
        # NB: 이 메서드 이름은 절대 ``_render``로 두면 안 된다 — Textual Widget의 예약
        # 메서드 _render(self)를 오버라이드해 None을 반환하게 되어, 렌더 시
        # ``'NoneType' object has no attribute 'render_strips'``로 위젯이 죽는다.
        # mount 전(위젯 트리 미구성)에 focus_worker/append 등이 불릴 수 있다 — 그땐
        # 조용히 건너뛴다(다음 _repaint나 on_mount 시 다시 그려짐).
        self._render_title()
        try:
            body = self.query_one("#console-body", Static)
        except Exception:
            return
        lines = self._buffers.get(self._shown or "", [])
        body.update("\n".join(lines) if lines else _EMPTY)
        try:
            self.scroll_end(animate=False)
        except Exception:
            pass

    def on_mount(self) -> None:
        # mount 완료 후 한 번 그려, mount 전에 들어온 버퍼/선택을 반영한다.
        self._repaint()
