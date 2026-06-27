"""UMC 팀 관제 대시보드 (Textual TUI) — Stage 0: read-only.

한 화면에서 8 워커·미리알림 백로그·inbox 메시지 흐름·승격 후보를 본다.
8개 tmux 창을 왔다갔다 하던 것을 이 대시보드 하나로 대체한다.

실행:  tools/umc-dashboard/.venv/bin/python tools/umc-dashboard/app.py
종료:  q   |   새로고침: r (자동 새로고침 3초)

진실원천은 .team/ store. 이 단계는 아무것도 쓰지 않는다(읽기만).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header

import store
from adapters import TeamCli
from widgets import AgentGrid, BacklogBoard, InboxTimeline, CandidateQueue


REFRESH_SECONDS = 3.0


class Dashboard(App):
    CSS = """
    Screen { layout: horizontal; }
    #sidebar { width: 34; border-right: solid $accent; }
    #main { width: 1fr; }
    #top { height: 1fr; }
    #bottom { height: 1fr; border-top: solid $accent; }
    .panel-title { background: $boost; color: $text; text-style: bold; padding: 0 1; }
    AgentGrid { height: 1fr; }
    """

    BINDINGS = [
        Binding("q", "quit", "종료"),
        Binding("r", "refresh", "새로고침"),
    ]

    backlog_open = reactive(0)

    def __init__(self) -> None:
        super().__init__()
        self.root = store.repo_root()
        self.cli = TeamCli(self.root)
        self.reminders_list = self._reminders_list_name()

    def _reminders_list_name(self) -> str:
        data = store._load_json(self.root / ".team" / "team.json") or {}
        return data.get("reminders_list") or "umc"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield AgentGrid(id="agents")
            with Vertical(id="main"):
                with Vertical(id="top"):
                    yield BacklogBoard(id="backlog")
                with Vertical(id="bottom"):
                    with Horizontal():
                        yield InboxTimeline(id="inbox")
                        yield CandidateQueue(id="candidates")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "UMC 팀 관제"
        self.refresh_data()
        self.set_interval(REFRESH_SECONDS, self.refresh_data)

    def action_refresh(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        snap = store.read_snapshot(self.root)
        self.query_one(AgentGrid).update_snapshot(snap)
        self.query_one(InboxTimeline).update_snapshot(snap)
        self.query_one(CandidateQueue).update_snapshot(snap)
        # Reminders backlog via the bridge CLI (osascript) — read-only pull.
        res = self.cli.reminders_pull(self.reminders_list)
        tasks = res.data if res.ok and isinstance(res.data, list) else []
        self.query_one(BacklogBoard).update_data(self.reminders_list, tasks, snap.goals, ok=res.ok, error=res.error)
        self.sub_title = f"{self.root.name}  ·  미리알림:{self.reminders_list}  ·  inbox {len(snap.inbox)}"


if __name__ == "__main__":
    Dashboard().run()
