"""조작용 모달 화면들 — 입력을 받아 콜백으로 결과를 돌려준다.

UI는 입력만 모으고, 실제 실행(CLI/tmux 호출)은 app.py가 콜백에서 한다 — 위젯은 얇게.
"""
from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, TextArea


class _BaseModal(ModalScreen):
    """입력을 모아 payload를 만들고 콜백으로 넘기는 모달 베이스.

    하위 모달은 ``_collect()``만 구현한다(유효하면 dict, 아니면 None).
    확인은 Enter 또는 [확인] 버튼, 취소는 Esc 또는 [취소] 버튼.
    """

    CSS = """
    _BaseModal { align: center middle; }
    #box { width: 70; height: auto; max-height: 80%; border: thick $accent; background: $surface; padding: 1 2; }
    #box Label { margin-top: 1; }
    #buttons { margin-top: 1; height: auto; align-horizontal: right; }
    #buttons Button { margin-left: 1; }
    #presets { height: auto; align-horizontal: left; }
    #presets Button { margin-right: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "취소"),
        Binding("ctrl+s", "submit", "확인"),
    ]

    def __init__(self, on_submit: Callable[[dict], None]):
        super().__init__()
        self._on_submit = on_submit
        self._closed = False  # 재진입 가드: _close는 모달당 정확히 1회만 효력

    def _collect(self) -> dict | None:
        """하위 클래스가 구현: 유효 입력이면 payload, 아니면 None."""
        return None

    def action_submit(self) -> None:
        self._close(self._collect())

    def action_cancel(self) -> None:
        self._close(None)

    def on_button_pressed(self, e: Button.Pressed) -> None:
        # 이벤트 버블링을 끊는다 — 모달이 dismiss된 뒤에도 큐에 남은 Pressed가
        # 부모/재처리되어 _close가 두 번 불리는 것을 차단(ScreenStackError 예방).
        e.stop()
        if e.button.id == "ok":
            self.action_submit()
        else:
            self.action_cancel()

    def _close(self, payload: dict | None) -> None:
        # 재진입 가드: 버튼 Pressed와 키 바인딩(Enter/Esc/ctrl+s)이 같은 턴에 겹쳐
        # _close가 두 번 불리면, 두 번째 dismiss는 이미 pop된 빈 스택을 또 pop하려다
        # ScreenStackError를 낸다. 모달당 1회만 효력을 갖게 막는다.
        if self._closed:
            return
        # 이 모달이 현재 스택 맨 위(활성)일 때만 dismiss가 안전하다. push_screen으로
        # 떠 있지 않거나 이미 닫힌 상태면 조용히 무시(방어적).
        if not self.is_current:
            self._closed = True
            return
        self._closed = True
        # 콜백을 dismiss보다 먼저 호출한다. dismiss()가 화면을 pop한 뒤에
        # 콜백을 부르면 끊긴 컨텍스트에서 후속 push_screen/refresh가 무시된다.
        if payload is not None:
            self._on_submit(payload)
        self.dismiss()


class SendMessageModal(_BaseModal):
    """워커 tmux 창에 주입할 메시지 입력."""

    def __init__(self, worker: str, on_submit):
        super().__init__(on_submit)
        self.worker = worker

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Label(f"[b]{self.worker}[/b] 에 메시지 주입")
            yield TextArea(id="msg")
            with Horizontal(id="buttons"):
                yield Button("취소", id="cancel")
                yield Button("보내기", id="ok", variant="primary")

    def _collect(self) -> dict | None:
        text = self.query_one("#msg", TextArea).text.strip()
        return {"text": text} if text else None


class InstructModal(_BaseModal):
    """headless 워커에게 보낼 작업 지시 입력 (새 대화 or resume).

    자유 프롬프트(TextArea) 외에 정형 액션 버튼 2개를 제공한다. 버튼을 누르면
    해당 워커의 팀(``team``)을 채운 정해진 프롬프트를 TextArea에 적어 넣을 뿐,
    바로 보내지 않는다 — 사용자가 검토·수정한 뒤 [지시]로 확정한다(자유입력 유지).
    """

    def __init__(self, worker: str, on_submit, *, resuming: bool = False, team: str = ""):
        super().__init__(on_submit)
        self.worker = worker
        self.resuming = resuming
        self.team = team

    def _preset(self, key: str) -> str:
        """정형 액션 프롬프트. 팀 메일박스 + claim 모델 + 미리알림 두 채널."""
        team = self.team or "?"
        rlist = f"umc-{team}"
        if key == "inbox":
            return (
                f"네 팀({team})의 받은편지함을 확인할 차례다. "
                f"`team-inbox` 스킬의 team_inbox.py로 팀 메일박스 "
                f"(받는주소 = 팀 '{team}')의 미소비 메시지를 read 하고, "
                f"제목·본문을 보고 너에게 할당된 메시지면 claim해서 처리한 뒤 "
                f"그 메시지를 ack 해라(이미 처리됐거나 네 담당이 아니면 손대지 마라). "
                f"처리 결과는 발신 팀에게 회신(post)하고, 무엇을 claim·처리·회신했는지 "
                f"한국어로 짧게 보고해라."
            )
        if key == "reminders":
            return (
                f"`reminders-team-bridge` 스킬의 reminders_bridge.py로 "
                f"미리알림 목록 '{rlist}'(= 네 팀 {team}의 백로그)를 pull 해서 "
                f"열린 작업을 확인하고, 네가 지금 착수할 다음 할 일을 한국어로 보고해라. "
                f"진행한 작업이 있으면 annotate로 진행 메모를 남기고 끝난 작업은 complete 해라."
            )
        return ""

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            mode = "이어서 지시(resume)" if self.resuming else "새 대화로 지시"
            team_tag = f" [dim]({self.team})[/dim]" if self.team else ""
            yield Label(f"[b]{self.worker}[/b]{team_tag} — {mode}")
            yield Label("정형 액션 (누르면 프롬프트가 아래에 채워짐 — 수정 후 지시)")
            with Horizontal(id="presets"):
                yield Button("inbox 확인·처리", id="preset-inbox")
                yield Button("리마인더 확인", id="preset-reminders")
            yield Label("프롬프트 (자유 입력)")
            yield TextArea(id="prompt")
            with Horizontal(id="buttons"):
                yield Button("취소", id="cancel")
                yield Button("지시", id="ok", variant="primary")

    def on_button_pressed(self, e: Button.Pressed) -> None:
        # 정형 액션 버튼은 submit/cancel이 아니라 TextArea를 채우고 머문다.
        if e.button.id == "preset-inbox":
            e.stop()
            self._fill("inbox")
        elif e.button.id == "preset-reminders":
            e.stop()
            self._fill("reminders")
        else:
            super().on_button_pressed(e)  # ok/cancel — super가 e.stop() 처리

    def _fill(self, key: str) -> None:
        ta = self.query_one("#prompt", TextArea)
        ta.text = self._preset(key)
        ta.focus()

    def _collect(self) -> dict | None:
        text = self.query_one("#prompt", TextArea).text.strip()
        return {"prompt": text} if text else None


class PostInboxModal(_BaseModal):
    """inbox 메시지 발행 — 수신자·제목·본문."""

    def __init__(self, sender: str, workers: list[str], on_submit, *, default_to: str = ""):
        super().__init__(on_submit)
        self.sender = sender
        self._workers = workers  # 'workers'는 Textual 노드의 read-only 속성과 충돌
        self.default_to = default_to

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Label(f"[b]inbox 발행[/b]  (from {self.sender})")
            yield Label("받는 사람")
            yield Select([(w, w) for w in self._workers],
                         value=self.default_to or Select.BLANK, id="to")
            yield Label("제목")
            yield Input(id="subject")
            yield Label("본문")
            yield TextArea(id="body")
            with Horizontal(id="buttons"):
                yield Button("취소", id="cancel")
                yield Button("발행", id="ok", variant="primary")

    def _collect(self) -> dict | None:
        to = self.query_one("#to", Select).value
        subject = self.query_one("#subject", Input).value.strip()
        body = self.query_one("#body", TextArea).text.strip()
        if to is Select.BLANK or not subject:
            return None
        return {"to": [str(to)], "subject": subject, "body": body}


class AddTaskModal(_BaseModal):
    """미리알림 백로그에 작업 추가 — 제목·우선순위."""

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Label("[b]미리알림 작업 추가[/b]")
            yield Label("제목")
            yield Input(id="title")
            yield Label("우선순위")
            yield Select([("없음", 0), ("낮음(1)", 1), ("보통(5)", 5), ("높음(9)", 9)],
                         value=0, id="priority", allow_blank=False)
            with Horizontal(id="buttons"):
                yield Button("취소", id="cancel")
                yield Button("추가", id="ok", variant="primary")

    def _collect(self) -> dict | None:
        title = self.query_one("#title", Input).value.strip()
        priority = self.query_one("#priority", Select).value
        return {"title": title, "priority": int(priority) or None} if title else None


class ConfirmModal(_BaseModal):
    """예/아니오 확인 — 사유 입력 옵션(거절 등)."""

    def __init__(self, prompt: str, on_submit, *, ask_reason: bool = False):
        super().__init__(on_submit)
        self.prompt = prompt
        self.ask_reason = ask_reason

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Label(self.prompt)
            if self.ask_reason:
                yield Label("사유")
                yield Input(id="reason")
            with Horizontal(id="buttons"):
                yield Button("아니오", id="cancel")
                yield Button("예", id="ok", variant="primary")

    def _collect(self) -> dict | None:
        reason = self.query_one("#reason", Input).value.strip() if self.ask_reason else ""
        return {"confirmed": True, "reason": reason}
