"""사이드바: 8 워커를 팀별로 묶은 선택 가능한 리스트.

8개 tmux 창을 이 그리드 하나가 대체. 워커를 선택하면 app이 조작 키
(구동/메시지/인터럽트/포커스)를 그 워커에 적용한다. 떠 있는 워커는 ● 배지.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

import store

TEAM_LABEL = {"data": "데이터", "write": "문서", "scout": "선행", "review": "검증"}


class AgentGrid(OptionList):
    """팀 → 워커. OptionList로 키보드/마우스 선택. id=워커명, 헤더는 disabled."""

    class WorkerSelected(Message):
        def __init__(self, worker: str, team: str) -> None:
            self.worker = worker
            self.team = team
            super().__init__()

    def __init__(self, **kw):
        super().__init__(**kw)
        self._team_of: dict[str, str] = {}
        self._running: set[str] = set()

    def update_snapshot(self, snap: "store.Snapshot", running: set[str] | None = None) -> None:
        self._running = running or set()
        self._team_of = {w.name: w.team for w in snap.workers}
        prev = self.highlighted  # 선택 유지
        self.clear_options()
        if not snap.workers:
            self.add_option(Option("로스터 없음", disabled=True))
            return

        order = [st.name for st in snap.subteams] or ["?"]
        by_team: dict[str, list[store.Worker]] = {}
        for w in snap.workers:
            by_team.setdefault(w.team, []).append(w)

        opts: list[Option] = []
        for team in order:
            members = by_team.get(team, [])
            if not members:
                continue
            opts.append(Option(f"[b]▌ {TEAM_LABEL.get(team, team)}[/b] [dim]({team})[/dim]", disabled=True))
            for w in members:
                star = "[yellow]★[/yellow]" if w.is_orchestrator else " "
                live = "[green]●[/green]" if w.name in self._running else "[dim]○[/dim]"
                unread = snap.unread_count_for(w.name)
                badge = f"[on red] {unread} [/]" if unread else ""
                opts.append(Option(f"{live} {star} {w.name} {badge}", id=w.name))
        for o in opts:
            self.add_option(o)
        if prev is not None and prev < self.option_count:
            self.highlighted = prev

    def on_option_list_option_selected(self, e: OptionList.OptionSelected) -> None:
        wid = e.option.id
        if wid and wid in self._team_of:
            self.post_message(self.WorkerSelected(wid, self._team_of[wid]))

    @property
    def selected_worker(self) -> tuple[str, str] | None:
        """현재 하이라이트된 워커(이름, 팀) — 조작 키의 대상."""
        if self.highlighted is None:
            return None
        opt = self.get_option_at_index(self.highlighted)
        wid = opt.id
        if wid and wid in self._team_of:
            return wid, self._team_of[wid]
        return None
