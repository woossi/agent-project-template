"""중앙 하단(좌 대체 가능): 선택한 워커와의 headless 대화 콘솔.

tmux 창을 들여다보던 것을 대체한다. 워커에게 보낸 지시와, 워커가 stream-json으로
돌려준 응답(텍스트·도구사용·완료)을 시간순으로 그린다. app이 이벤트가 도착할 때마다
append_event()를 호출한다(워커 스레드 → call_from_thread).
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


class WorkerConsole(VerticalScroll):
    """선택 워커와의 대화 로그. 지시(나)와 응답(워커)을 한 흐름으로."""

    MAX_LINES = 400

    def __init__(self, **kw):
        super().__init__(**kw)
        self._worker: str | None = None
        self._lines: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static("워커 콘솔", classes="panel-title")
        yield Static("[dim]워커를 선택하고 'c'로 지시하세요[/dim]", id="console-body")

    def focus_worker(self, worker: str | None) -> None:
        """표시 대상 워커를 바꾼다(로그는 워커별로 분리해 보관하지 않고 단순화:
        지시할 때마다 헤더로 구분). 여기서는 현재 대상만 추적한다."""
        self._worker = worker

    def add_prompt(self, worker: str, prompt: str) -> None:
        self._worker = worker
        self._lines.append(f"\n[b on grey23] ▶ {worker} 에게 지시 [/]")
        self._lines.append(f"[white]{prompt}[/white]")
        self._flush()

    def append_event(self, ev: WorkerEvent) -> None:
        icon = _ICON.get(ev.kind, "·")
        text = ev.text.strip()
        if not text:
            return
        # assistant 본문은 여러 줄일 수 있다 — 그대로, 나머지는 한 줄.
        self._lines.append(f"{icon} {text}")
        self._flush()

    def add_status(self, msg: str, *, ok: bool = True) -> None:
        mark = "[blue]✓[/blue]" if ok else "[red]✗[/red]"
        self._lines.append(f"{mark} [dim]{msg}[/dim]")
        self._flush()

    def _flush(self) -> None:
        if len(self._lines) > self.MAX_LINES:
            self._lines = self._lines[-self.MAX_LINES:]
        body = self.query_one("#console-body", Static)
        body.update("\n".join(self._lines) if self._lines else
                    "[dim]워커를 선택하고 'c'로 지시하세요[/dim]")
        self.scroll_end(animate=False)
