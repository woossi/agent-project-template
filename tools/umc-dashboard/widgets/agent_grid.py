"""사이드바: 8 워커를 팀별로 묶어 카드로. 8개 tmux 창을 이 그리드 하나가 대체."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

import store

TEAM_LABEL = {"data": "데이터", "write": "문서", "scout": "선행", "review": "검증"}


class AgentGrid(VerticalScroll):
    """팀 → 워커 카드. unread 메시지 수를 상태 배지로."""

    def compose(self) -> ComposeResult:
        yield Static("에이전트", classes="panel-title")
        yield Static("(로딩…)", id="agent-body")

    def update_snapshot(self, snap: "store.Snapshot") -> None:
        body = self.query_one("#agent-body", Static)
        if not snap.workers:
            body.update("[dim]로스터 없음[/dim]")
            return

        # 팀별로 그룹화 (subteams 순서 유지)
        order = [st.name for st in snap.subteams] or ["?"]
        by_team: dict[str, list[store.Worker]] = {t: [] for t in order}
        for w in snap.workers:
            by_team.setdefault(w.team, []).append(w)

        lines: list[str] = []
        for team in order:
            members = by_team.get(team, [])
            if not members:
                continue
            lines.append(f"[b]▌ {TEAM_LABEL.get(team, team)}[/b] [dim]({team})[/dim]")
            for w in members:
                star = "[yellow]★[/yellow]" if w.is_orchestrator else " "
                unread = snap.unread_count_for(w.name)
                if unread > 0:
                    badge = f"[on red] {unread} [/]"
                else:
                    badge = "[dim] · [/dim]"
                lines.append(f"  {star} {w.name}  {badge}")
                if w.role:
                    lines.append(f"     [dim]{w.role[:30]}[/dim]")
            lines.append("")
        body.update("\n".join(lines).rstrip())
