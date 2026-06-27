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
    """

    BINDINGS = [
        Binding("escape", "cancel", "취소"),
        Binding("ctrl+s", "submit", "확인"),
    ]

    def __init__(self, on_submit: Callable[[dict], None]):
        super().__init__()
        self._on_submit = on_submit

    def _collect(self) -> dict | None:
        """하위 클래스가 구현: 유효 입력이면 payload, 아니면 None."""
        return None

    def action_submit(self) -> None:
        self._close(self._collect())

    def action_cancel(self) -> None:
        self._close(None)

    def on_button_pressed(self, e: Button.Pressed) -> None:
        if e.button.id == "ok":
            self.action_submit()
        else:
            self.action_cancel()

    def _close(self, payload: dict | None) -> None:
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
