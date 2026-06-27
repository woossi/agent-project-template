"""중앙 하단(우): 승격·파생 후보 큐.

detect_*가 additionalContext로 모델에만 띄우던 후보를 사람에게 보여준다.
(승격/거절 버튼은 1단계에서 resolve CLI 호출로 연결.)
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

import store

KIND_LABEL = {
    "skill": "스킬", "agent": "에이전트",
    "team_skill": "팀스킬", "team_agent": "팀에이전트",
    "term": "용어", "preference": "선호", "memory": "메모리",
}


class CandidateQueue(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static("승격 · 파생 후보", classes="panel-title")
        yield Static("(로딩…)", id="cand-body")

    def update_snapshot(self, snap: "store.Snapshot") -> None:
        body = self.query_one("#cand-body", Static)
        if not snap.candidates:
            body.update("[dim]후보 없음[/dim]")
            return
        lines: list[str] = []
        for c in snap.candidates:
            label = KIND_LABEL.get(c.kind, c.kind)
            key = c.key if len(c.key) <= 46 else c.key[:43] + "…"
            lines.append(f"[yellow]◆[/yellow] [b]{label}[/b]  {key}")
            if c.detail:
                lines.append(f"   [dim]{c.detail[:50]} · {c.source}[/dim]")
        body.update("\n".join(lines))
