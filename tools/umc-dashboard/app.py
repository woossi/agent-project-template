"""UMC 팀 관제 대시보드 (Textual TUI).

한 화면에서 8 워커·미리알림 백로그·inbox 흐름·승격 후보를 보고 조작한다.
8개 tmux 창을 왔다갔다 하던 것을 이 대시보드 하나로 대체.

진실원천은 .project/ store. 쓰기는 전부 검증된 CLI(adapters)·tmux(launcher) 위임.

조작 키 (전원 headless — tmux 별창 없음):
  워커(사이드바 선택 후):  c 지시 · g 팀일괄구동(팀 전원 깨워 메일박스 claim) · x 세션리셋
  미리알림:  a 작업추가
  inbox:     p 팀 메일박스 발행
  후보:      P 승격 · D 거절
  공통:      r 새로고침 · q 종료
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header

import store
from adapters import TeamCli
from launcher import TmuxLauncher
from session_pool import SessionPool
from worker_session import WorkerEvent
from widgets import (AgentGrid, BacklogBoard, InboxTimeline, CandidateQueue,
                     WorkerConsole, ResourceStrip)
from widgets.modals import (PostInboxModal, AddTaskModal,
                            ConfirmModal, InstructModal, preset_prompt)

# 빠른 갱신(파일 store + tmux)만 자동으로 3초마다 돈다. Apple Reminders 조회는
# osascript로 수십 초까지 걸려 UI를 얼리므로 자동 폴링에서 제외하고, 'R' 키로
# 명시 요청할 때만 백그라운드 스레드에서 당겨온다(낙관적 추가는 그 사이 즉시 반영).
REFRESH_SECONDS = 3.0


class Dashboard(App):
    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; layout: horizontal; }
    #sidebar { width: 36; border-right: solid $accent; }
    #main { width: 1fr; }
    #right { width: 44; border-left: solid $accent; }
    #top { height: 45%; }
    #bottom { height: 55%; border-top: solid $accent; }
    #cand-pane { height: 45%; }
    #console-pane { height: 55%; border-top: solid $accent; }
    #strip { height: 4; border-top: solid $accent; background: $boost; }
    .panel-title { background: $boost; color: $text; text-style: bold; padding: 0 1; }
    AgentGrid { height: 1fr; border: none; }
    WorkerConsole { width: 1fr; height: 1fr; }
    InboxTimeline { width: 1fr; }
    CandidateQueue { width: 1fr; height: 1fr; }
    ResourceStrip Static { width: 1fr; padding: 0 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "종료"),
        Binding("r", "refresh", "새로고침"),
        Binding("R", "pull_reminders", "미리알림당기기"),
        Binding("c", "instruct", "지시"),
        Binding("g", "instruct_team", "팀일괄구동"),
        Binding("x", "reset_session", "세션리셋"),
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
        self.pool = SessionPool(self.root)  # headless 워커 세션(멀티턴)
        self.reminders_list = self._reminders_list_name()
        self._snap: store.Snapshot | None = None
        # Reminders 조회는 비싸므로(osascript 수십 초) 마지막 결과를 캐시한다.
        # 자동 갱신(refresh_data)은 이 캐시만 그리고, 'R' 키로만 실제로 다시 당긴다.
        self._tasks: list[dict] = []
        self._tasks_ok: bool = True
        self._tasks_error: str = ""
        self._tasks_pulled: bool = False  # 아직 한 번도 안 당김
        self._pulling: bool = False       # 백그라운드 당기기 진행 중(중복 방지)
        self._instructing: set[str] = set()  # 가동 중인 워커 집합(워커별 동시 지시 허용)

    def _reminders_list_name(self) -> str:
        data = store._load_json(self.root / ".project" / "team.json") or {}
        return data.get("reminders_list") or "umc"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        # 3열: 좌 워커 · 중앙 보드(상 백로그/하 inbox 전이) · 우 후보+콘솔.
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield AgentGrid(id="agents")
            with Vertical(id="main"):
                with Vertical(id="top"):
                    yield BacklogBoard(id="backlog")
                with Vertical(id="bottom"):
                    yield InboxTimeline(id="inbox")
            with Vertical(id="right"):
                with Vertical(id="cand-pane"):
                    yield CandidateQueue(id="candidates")
                with Vertical(id="console-pane"):
                    yield WorkerConsole(id="console")
        # 하단 풀폭: 팀 부하 현재량 스트립.
        yield ResourceStrip(id="strip")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "UMC 팀 관제"
        self.refresh_data()
        self.set_interval(REFRESH_SECONDS, self.refresh_data)

    # ---------------- refresh ----------------

    def refresh_data(self) -> None:
        """빠른 갱신만: 파일 store + tmux. Reminders는 건드리지 않고 캐시만 그린다."""
        snap = store.read_snapshot(self.root)
        self._snap = snap
        # ● 배지 = tmux 창이 떠 있거나(대화형) headless 세션이 살아있는(멀티턴) 워커.
        running = self.launcher.running_workers() | self.pool.active_workers()
        self.query_one(AgentGrid).update_snapshot(snap, running=running)
        self.query_one(InboxTimeline).update_snapshot(snap)
        self.query_one(CandidateQueue).update_snapshot(snap)
        self._render_backlog()
        self._render_strip(snap)
        tmux_ok, tmux_why = self.launcher.available()
        tmux_s = f"tmux {len(running)}개 실행" if tmux_ok else f"tmux:{tmux_why}"
        self.sub_title = (f"{self.root.name} · 미리알림:{self.reminders_list} · "
                          f"inbox {len(snap.inbox)} · {tmux_s}")

    def _render_strip(self, snap: "store.Snapshot") -> None:
        """팀 부하 현재량 스트립. 전부 store/세션풀에서 결정적으로 나오는 절대량."""
        unread = sum(1 for m in snap.inbox if not m.consumed)
        active = len(self.pool.active_workers())
        # 미완 백로그: 미리알림을 아직 안 당겼으면 0(캐시 비어있음). 당긴 뒤에만 의미.
        open_backlog = sum(1 for t in self._tasks if not t.get("completed"))
        self.query_one(ResourceStrip).update_data(
            unread=unread, active_sessions=active,
            worker_count=len(snap.workers), open_backlog=open_backlog)

    def _render_backlog(self) -> None:
        """캐시된 Reminders 작업으로 백로그를 그린다(네트워크/osascript 호출 없음)."""
        goals = self._snap.goals if self._snap else []
        if self._pulling:
            board_error = "미리알림 당기는 중…"
        elif not self._tasks_pulled:
            board_error = "R 키로 미리알림을 당기세요(아직 미조회)"
        else:
            board_error = self._tasks_error
        self.query_one(BacklogBoard).update_data(
            self.reminders_list, self._tasks, goals,
            ok=self._tasks_ok, error=board_error)

    def action_refresh(self) -> None:
        self.refresh_data()

    def on_agent_grid_worker_selected(self, ev: "AgentGrid.WorkerSelected") -> None:
        """사이드바에서 워커를 고르면 콘솔 표시 대상을 그 워커로."""
        self.query_one(WorkerConsole).focus_worker(ev.worker)

    # ---------------- reminders pull (느림 — 명시 요청 시에만, 백그라운드) ----------------

    def action_pull_reminders(self) -> None:
        if self._pulling:
            self._toast(False, "이미 미리알림을 당기는 중입니다")
            return
        self._pulling = True
        self._render_backlog()  # "당기는 중…" 표시
        self._toast(True, "미리알림 당기는 중… (수십 초 걸릴 수 있음)")
        self._pull_reminders_worker()

    def _apply_pull(self, ok: bool, tasks: list, error: str) -> None:
        """워커 스레드 결과를 메인 스레드에서 반영."""
        self._pulling = False
        self._tasks_pulled = True
        self._tasks_ok = ok
        self._tasks_error = error
        if ok:
            self._tasks = tasks
        self._render_backlog()
        self._toast(ok, f"미리알림 {len(tasks)}건 반영" if ok else f"당기기 실패: {error}")

    @work(thread=True, exclusive=True, group="reminders")
    def _pull_reminders_worker(self) -> None:
        """별도 스레드에서 osascript 호출(수십 초). UI 이벤트 루프는 안 막힌다."""
        res = self.cli.reminders_pull(self.reminders_list)
        tasks = res.data if res.ok and isinstance(res.data, list) else []
        self.call_from_thread(self._apply_pull, res.ok, tasks, res.error)

    # ---------------- helpers ----------------

    def _selected_worker(self) -> tuple[str, str] | None:
        return self.query_one(AgentGrid).selected_worker

    def _worker_names(self) -> list[str]:
        return [w.name for w in (self._snap.workers if self._snap else [])]

    def _team_names(self) -> list[str]:
        # 팀 전용 메일박스 모델: 발행 수신자는 팀(+ orchestrator 가상 메일박스).
        teams = [t.name for t in (self._snap.subteams if self._snap else [])]
        return teams + ["orchestrator"]

    def _toast(self, ok: bool, msg: str) -> None:
        self.notify(msg, severity="information" if ok else "error",
                    timeout=4)

    # ---------------- headless 워커 지시 (subprocess: claude --print) ----------------
    # (tmux 별창 구동 l/f/m/i는 2026-06-27 headless 통일로 제거 — 모든 워커는 대시보드
    #  안에서 headless로 구동·응답 수신한다. TmuxLauncher 코드는 남겨 두되 UI 경로 없음.)

    def action_instruct(self) -> None:
        """선택 워커에게 headless 지시. tmux 없이 직접 구동·응답 수신."""
        sel = self._selected_worker()
        if not sel:
            self._toast(False, "워커를 먼저 선택하세요(사이드바)")
            return
        worker, team = sel
        # 워커별 락: 같은 워커가 이미 가동 중이면만 막고, 다른 팀/워커는 동시 지시 허용.
        if worker in self._instructing:
            self._toast(False, f"{worker} 지시 처리 중 — 끝나면 다시")
            return
        resuming = self.pool.has_session(worker)
        console = self.query_one(WorkerConsole)
        console.focus_worker(worker)

        def submit(payload: dict) -> None:
            prompt = payload["prompt"]
            console.add_prompt(worker, prompt)
            self._instructing.add(worker)
            console.set_active(worker, True)
            self._instruct_worker(worker, team, prompt)

        self.push_screen(InstructModal(worker, submit, resuming=resuming, team=team))

    def action_instruct_team(self) -> None:
        """선택 워커가 속한 팀의 모든 워커를 동시에 headless로 깨워, 각자 '팀 메일박스
        확인·claim·처리' inbox preset을 일괄 지시한다. 리더가 발행한 작업이 메일박스에
        쌓여만 있고 아무도 안 가져가던 문제(active 0)를 푼다 — 워커들이 자기 담당을 claim."""
        sel = self._selected_worker()
        if not sel:
            self._toast(False, "워커를 먼저 선택하세요(그 워커의 팀 전체를 구동)")
            return
        _, team = sel
        members = self._team_members(team)
        if not members:
            self._toast(False, f"팀 '{team}' 멤버를 찾을 수 없음")
            return
        console = self.query_one(WorkerConsole)
        launched, skipped = [], []
        for w in members:
            if w in self._instructing:
                skipped.append(w)
                continue
            prompt = preset_prompt("inbox", worker=w, team=team)
            console.add_prompt(w, prompt)
            self._instructing.add(w)
            console.set_active(w, True)
            self._instruct_worker(w, team, prompt)
            launched.append(w)
        msg = f"팀 {team} 일괄구동: {len(launched)}명" + (f" (가동중 {len(skipped)} 건너뜀)" if skipped else "")
        self._toast(bool(launched), msg)

    def _team_members(self, team: str) -> list[str]:
        for st in (self._snap.subteams if self._snap else []):
            if st.name == team:
                return list(st.members)
        return []

    def action_reset_session(self) -> None:
        """선택 워커의 headless 대화를 새로 시작(다음 지시는 새 세션)."""
        sel = self._selected_worker()
        if not sel:
            return
        worker, _ = sel
        self.pool.reset(worker)
        self.query_one(WorkerConsole).add_status(f"{worker} 세션 리셋 — 다음 지시는 새 대화")
        self._toast(True, f"{worker} 세션 리셋")

    def _on_worker_event(self, worker: str, ev: WorkerEvent) -> None:
        """워커 스레드에서 도착한 이벤트를 그 워커 버퍼에 그린다(메인 스레드)."""
        self.query_one(WorkerConsole).append_event(worker, ev)

    def _on_turn_done(self, worker: str, ok: bool, error: str) -> None:
        self._instructing.discard(worker)
        console = self.query_one(WorkerConsole)
        console.set_active(worker, False)
        if ok:
            console.add_status(worker, f"{worker} 턴 완료")
        else:
            console.add_status(worker, f"{worker} 실패: {error}", ok=False)
        self._toast(ok, f"{worker} 응답 완료" if ok else f"{worker} 실패: {error}")
        self.refresh_data()  # active 세션 배지 갱신

    @work(thread=True, exclusive=False)
    def _instruct_worker(self, worker: str, team: str, prompt: str) -> None:
        """별도 스레드에서 headless claude를 구동(블로킹). UI는 안 막힌다.
        exclusive=False라 호출마다 독립 스레드로 동시 실행된다 — 여러 워커/팀을 동시에
        가동할 수 있다(이전엔 단일 _instructing 락이 직렬화했다). 워커별 중복은
        action_instruct의 set 락이 막고, 출력은 워커별 콘솔 버퍼로 분리된다."""
        def emit(ev: WorkerEvent) -> None:
            self.call_from_thread(self._on_worker_event, worker, ev)
        r = self.pool.send(worker, team, prompt, on_event=emit)
        self.call_from_thread(self._on_turn_done, worker, r.ok, r.error)

    # ---------------- inbox (stage 1: CLI) ----------------

    def action_post_inbox(self) -> None:
        teams = self._team_names()
        if not teams:
            return
        # 선택된 워커가 있으면 그 워커의 팀을 기본 수신 팀으로.
        default_to = ""
        sel = self._selected_worker()
        if sel:
            default_to = sel[1] or ""  # (worker, team)

        def submit(payload: dict) -> None:
            to_team = payload["to_team"]
            r = self.cli.inbox_post("orchestrator", to_team,
                                    payload["subject"], payload["body"])
            self._toast(r.ok, f"발행 → 팀 {to_team}" if r.ok else f"실패: {r.error}")
            self.refresh_data()

        self.push_screen(PostInboxModal("orchestrator", teams, submit, default_to=default_to))

    # ---------------- reminders (stage 1: CLI) ----------------

    def action_add_task(self) -> None:
        def submit(payload: dict) -> None:
            r = self.cli.reminders_add(self.reminders_list, payload["title"],
                                       priority=payload.get("priority"))
            if r.ok and self._tasks_pulled:
                # 낙관적 반영: R로 다시 당기기 전까지 새 작업을 캐시에 끼워 넣어 즉시 보이게.
                self._tasks.append({"name": payload["title"],
                                    "priority": payload.get("priority") or 0,
                                    "completed": False})
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
