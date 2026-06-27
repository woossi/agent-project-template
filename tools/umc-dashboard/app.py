"""UMC 팀 관제 대시보드 (Textual TUI).

한 화면에서 8 워커·미리알림 백로그·inbox 흐름·승격 후보를 보고 조작한다.
8개 tmux 창을 왔다갔다 하던 것을 이 대시보드 하나로 대체.

진실원천은 .team/ store. 쓰기는 전부 검증된 CLI(adapters)·tmux(launcher) 위임.

조작 키:
  워커(사이드바 선택 후):  l 구동 · f 포커스 · m 메시지 · i 인터럽트
  미리알림:  a 작업추가
  inbox:     p 메시지 발행
  후보:      P 승격 · D 거절
  공통:      r 새로고침 · q 종료
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header

import store
from adapters import TeamCli
from launcher import TmuxLauncher
from widgets import AgentGrid, BacklogBoard, InboxTimeline, CandidateQueue
from widgets.modals import SendMessageModal, PostInboxModal, AddTaskModal, ConfirmModal

REFRESH_SECONDS = 3.0


class Dashboard(App):
    CSS = """
    Screen { layout: horizontal; }
    #sidebar { width: 36; border-right: solid $accent; }
    #main { width: 1fr; }
    #top { height: 1fr; }
    #bottom { height: 1fr; border-top: solid $accent; }
    .panel-title { background: $boost; color: $text; text-style: bold; padding: 0 1; }
    AgentGrid { height: 1fr; border: none; }
    InboxTimeline { width: 1fr; }
    CandidateQueue { width: 1fr; }
    """

    BINDINGS = [
        Binding("q", "quit", "종료"),
        Binding("r", "refresh", "새로고침"),
        Binding("l", "launch", "구동"),
        Binding("f", "focus_worker", "포커스"),
        Binding("m", "message", "메시지"),
        Binding("i", "interrupt", "인터럽트"),
        Binding("a", "add_task", "작업추가"),
        Binding("p", "post_inbox", "발행"),
        Binding("P", "promote", "승격"),
        Binding("D", "decline", "거절"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.root = store.repo_root()
        self.cli = TeamCli(self.root)
        self.launcher = TmuxLauncher(self.root)
        self.reminders_list = self._reminders_list_name()
        self._snap: store.Snapshot | None = None

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

    # ---------------- refresh ----------------

    def refresh_data(self) -> None:
        snap = store.read_snapshot(self.root)
        self._snap = snap
        running = self.launcher.running_workers()
        self.query_one(AgentGrid).update_snapshot(snap, running=running)
        self.query_one(InboxTimeline).update_snapshot(snap)
        self.query_one(CandidateQueue).update_snapshot(snap)
        res = self.cli.reminders_pull(self.reminders_list)
        tasks = res.data if res.ok and isinstance(res.data, list) else []
        self.query_one(BacklogBoard).update_data(
            self.reminders_list, tasks, snap.goals, ok=res.ok, error=res.error)
        tmux_ok, tmux_why = self.launcher.available()
        tmux_s = f"tmux {len(running)}개 실행" if tmux_ok else f"tmux:{tmux_why}"
        self.sub_title = f"{self.root.name} · 미리알림:{self.reminders_list} · inbox {len(snap.inbox)} · {tmux_s}"

    def action_refresh(self) -> None:
        self.refresh_data()

    # ---------------- helpers ----------------

    def _selected_worker(self) -> tuple[str, str] | None:
        return self.query_one(AgentGrid).selected_worker

    def _worker_names(self) -> list[str]:
        return [w.name for w in (self._snap.workers if self._snap else [])]

    def _toast(self, ok: bool, msg: str) -> None:
        self.notify(msg, severity="information" if ok else "error",
                    timeout=4)

    # ---------------- worker ops (stage 2: tmux) ----------------

    def action_launch(self) -> None:
        sel = self._selected_worker()
        if not sel:
            self._toast(False, "워커를 먼저 선택하세요(사이드바)")
            return
        worker, team = sel
        r = self.launcher.launch(worker, team)
        self._toast(r.ok, f"구동: {worker} → {r.window}" if r.ok else f"구동 실패: {r.error}")
        self.refresh_data()

    def action_focus_worker(self) -> None:
        sel = self._selected_worker()
        if not sel:
            return
        worker, _ = sel
        r = self.launcher.focus(worker)
        if not r.ok:
            self._toast(False, f"포커스 실패: {r.error}")

    def action_interrupt(self) -> None:
        sel = self._selected_worker()
        if not sel:
            return
        worker, _ = sel
        r = self.launcher.interrupt(worker)
        self._toast(r.ok, f"인터럽트: {worker}" if r.ok else f"실패: {r.error}")

    def action_message(self) -> None:
        sel = self._selected_worker()
        if not sel:
            self._toast(False, "워커를 먼저 선택하세요")
            return
        worker, _ = sel

        def submit(payload: dict) -> None:
            r = self.launcher.send_message(worker, payload["text"])
            self._toast(r.ok, f"메시지 전송: {worker}" if r.ok else f"실패: {r.error}")

        self.push_screen(SendMessageModal(worker, submit))

    # ---------------- inbox (stage 1: CLI) ----------------

    def action_post_inbox(self) -> None:
        names = self._worker_names()
        if not names:
            return
        default_to = ""
        sel = self._selected_worker()
        if sel:
            default_to = sel[0]

        def submit(payload: dict) -> None:
            r = self.cli.inbox_post("orchestrator", payload["to"],
                                    payload["subject"], payload["body"])
            self._toast(r.ok, f"발행 → {','.join(payload['to'])}" if r.ok else f"실패: {r.error}")
            self.refresh_data()

        self.push_screen(PostInboxModal("orchestrator", names, submit, default_to=default_to))

    # ---------------- reminders (stage 1: CLI) ----------------

    def action_add_task(self) -> None:
        def submit(payload: dict) -> None:
            r = self.cli.reminders_add(self.reminders_list, payload["title"],
                                       priority=payload.get("priority"))
            self._toast(r.ok, f"작업 추가: {payload['title'][:30]}" if r.ok else f"실패: {r.error}")
            self.refresh_data()

        self.push_screen(AddTaskModal(submit))

    # ---------------- candidates (stage 1: resolve CLI) ----------------

    def _resolve_selected(self, decision: str) -> None:
        cand = self.query_one(CandidateQueue).selected
        if not cand:
            self._toast(False, "후보를 먼저 선택하세요")
            return
        is_team = cand.source.startswith("team-")
        is_derivation = "derivation" in cand.source

        def submit(payload: dict) -> None:
            if not payload.get("confirmed"):
                return
            reason = payload.get("reason", "")
            if is_derivation:
                r = self.cli.resolve_derivation(cand.kind, cand.key, decision, reason)
            else:
                r = self.cli.resolve_promotion(cand.kind, cand.key, decision, reason)
            verb = "승격" if decision == "promote" else "거절"
            self._toast(r.ok, f"{verb}: {cand.key[:30]}" if r.ok else f"실패: {r.error}")
            self.refresh_data()

        verb = "승격" if decision == "promote" else "거절"
        tier = "팀 " if is_team else ""
        self.push_screen(ConfirmModal(
            f"[b]{tier}{cand.kind}[/b] '{cand.key[:40]}' 을 {verb}할까요?",
            submit, ask_reason=(decision == "decline")))

    def action_promote(self) -> None:
        self._resolve_selected("promote")

    def action_decline(self) -> None:
        self._resolve_selected("decline")


if __name__ == "__main__":
    Dashboard().run()
