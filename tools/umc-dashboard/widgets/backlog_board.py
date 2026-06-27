"""중앙 상단: 미리알림 백로그(사람도 보는 작업 큐) + 팀 목표."""
from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

import store

PRIORITY_MARK = {9: "[red]!!![/red]", 5: "[yellow]!![/yellow]", 1: "[blue]![/blue]"}


class BacklogBoard(VerticalScroll):
    """미리알림 umc 목록의 할일과 목표를 한 패널에."""

    def compose(self) -> ComposeResult:
        yield Static("작업 · 목표", classes="panel-title")
        yield Static("(로딩…)", id="backlog-body")

    def update_data(self, list_name: str, tasks: list[dict[str, Any]],
                    goals: list["store.Goal"], *, ok: bool, error: str = "") -> None:
        body = self.query_one("#backlog-body", Static)
        lines: list[str] = []

        # 목표
        if goals:
            lines.append("[b]목표[/b]")
            for g in goals:
                sc = len(g.success_criteria)
                lines.append(f"  ◆ {g.title}  [dim]({g.status or '-'} · 기준 {sc})[/dim]")
            lines.append("")

        # 미리알림 백로그
        lines.append(f"[b]미리알림 백로그[/b] [dim]({list_name})[/dim]")
        if not ok:
            lines.append(f"  [red]미리알림 읽기 실패: {error or '권한(TCC) 확인'}[/red]")
        elif not tasks:
            lines.append("  [dim]열린 작업 없음[/dim]")
        else:
            for t in tasks:
                done = t.get("completed")
                check = "[green]✓[/green]" if done else "[ ]"
                pr = PRIORITY_MARK.get(t.get("priority") or 0, "")
                name = str(t.get("name", ""))[:70]
                due = t.get("due")
                due_s = f" [dim]→{str(due)[:10]}[/dim]" if due else ""
                lines.append(f"  {check} {pr} {name}{due_s}")

        body.update("\n".join(lines))
