"""중앙 하단(우): 승격·파생 후보 큐 (선택 가능).

detect_*가 모델에만 띄우던 후보를 사람에게. 선택 후 app이 승격/거절(resolve CLI)을 적용.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

import store

KIND_LABEL = {
    "skill": "스킬", "agent": "에이전트",
    "team_skill": "팀스킬", "team_agent": "팀에이전트",
    "term": "용어", "preference": "선호", "memory": "메모리",
}


class CandidateQueue(Vertical):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._candidates: list[store.Candidate] = []

    def compose(self) -> ComposeResult:
        yield Static("승격 · 파생 후보", classes="panel-title")
        yield OptionList(id="cand-list")

    def update_snapshot(self, snap: "store.Snapshot") -> None:
        self._candidates = snap.candidates
        ol = self.query_one("#cand-list", OptionList)
        prev = ol.highlighted
        ol.clear_options()
        if not snap.candidates:
            ol.add_option(Option("후보 없음", disabled=True))
            return
        for i, c in enumerate(snap.candidates):
            label = KIND_LABEL.get(c.kind, c.kind)
            key = c.key if len(c.key) <= 40 else c.key[:37] + "…"
            text = f"[yellow]◆[/yellow] [b]{label}[/b] {key}"
            if c.detail:
                text += f"\n   [dim]{c.detail[:46]}[/dim]"
            ol.add_option(Option(text, id=str(i)))
        if prev is not None and prev < ol.option_count:
            ol.highlighted = prev

    @property
    def selected(self) -> "store.Candidate | None":
        ol = self.query_one("#cand-list", OptionList)
        if ol.highlighted is None:
            return None
        opt = ol.get_option_at_index(ol.highlighted)
        if opt.id is None:
            return None
        try:
            return self._candidates[int(opt.id)]
        except (ValueError, IndexError):
            return None
