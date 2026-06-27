"""워커별 headless claude 세션 풀 — 대시보드가 여러 워커와 멀티턴 대화를 유지한다.

WorkerSession(worker_session.py)을 워커 이름으로 보관한다. 각 세션은 자기
session_id를 들고 있어 두 번째 턴부터 --resume으로 같은 대화를 잇는다.

send()는 subprocess(claude --print)를 블로킹으로 돌리므로, 여기서 직접 부르면
UI가 응답이 끝날 때까지(수십 초) 얼어붙는다. 그래서 대시보드는 이걸 Textual의
@work(thread=True) 워커 스레드에서 호출하고, on_event는 call_from_thread로
메인 스레드에 넘긴다(app.py가 처리). 이 모듈 자체는 스레드를 모른다 — 순수하게
세션 보관과 위임만 한다(테스트하기 쉽게).
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from worker_session import WorkerSession, WorkerEvent, TurnResult


class SessionPool:
    """worker 이름 → WorkerSession. 멀티턴 컨텍스트를 워커별로 유지한다."""

    def __init__(self, root: Path, *, permission_mode: str = "acceptEdits",
                 session_factory: Callable[..., WorkerSession] | None = None):
        self.root = root
        self.permission_mode = permission_mode
        self._factory = session_factory or WorkerSession
        self._sessions: dict[str, WorkerSession] = {}

    def session(self, worker: str, team: str) -> WorkerSession:
        """워커의 세션을 가져온다(없으면 생성). 같은 워커는 항상 같은 세션."""
        s = self._sessions.get(worker)
        if s is None:
            s = self._factory(worker, team, self.root,
                              permission_mode=self.permission_mode)
            self._sessions[worker] = s
        return s

    def has_session(self, worker: str) -> bool:
        """그 워커와 한 번이라도 대화해 session_id를 잡았는지."""
        s = self._sessions.get(worker)
        return bool(s and s.session_id)

    def send(self, worker: str, team: str, prompt: str,
             *, on_event: Callable[[WorkerEvent], None] | None = None,
             timeout: float | None = None) -> TurnResult:
        """워커에게 한 턴을 보낸다(블로킹). 호출자가 스레드로 감싼다."""
        return self.session(worker, team).send(prompt, on_event=on_event, timeout=timeout)

    def reset(self, worker: str) -> None:
        """워커 세션을 버린다 — 다음 send는 새 대화로 시작한다."""
        self._sessions.pop(worker, None)

    def active_workers(self) -> set[str]:
        """진행 중 대화(session_id 보유)가 있는 워커 집합 — 상태 배지용."""
        return {w for w, s in self._sessions.items() if s.session_id}
