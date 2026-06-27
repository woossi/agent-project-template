"""중앙 하단(좌): .project/inbox 다대다 메시지를 시간순으로.

사람이 8 터미널을 돌며 '누가 누구에게 무엇을 위임했나' 읽던 것을 한 흐름으로.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

import store


class InboxTimeline(VerticalScroll):
    MAX_ROWS = 40

    def compose(self) -> ComposeResult:
        yield Static("메시지 흐름 (inbox)", classes="panel-title")
        yield Static("(로딩…)", id="inbox-body")

    def update_snapshot(self, snap: "store.Snapshot") -> None:
        body = self.query_one("#inbox-body", Static)
        if not snap.inbox:
            body.update("[dim]메시지 없음[/dim]")
            return
        lines: list[str] = []
        for m in snap.inbox[: self.MAX_ROWS]:
            if m.consumed:
                state = "[dim]✓[/dim]"
                color = "dim"
            else:
                state = "[red]●[/red]"
                color = "white"
            subj = m.subject[:54] if m.subject else m.body[:54]
            lines.append(
                f"{state} [{color}][b]{m.sender}[/b]→{m.to}[/{color}]  {subj}"
            )
        more = len(snap.inbox) - self.MAX_ROWS
        if more > 0:
            lines.append(f"[dim]… 외 {more}건[/dim]")
        body.update("\n".join(lines))
