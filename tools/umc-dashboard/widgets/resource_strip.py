"""하단 풀폭: 팀 부하 '현재량' 스트립.

중요 — 이건 '한도 대비 점유율' 게이지가 아니다. 코드 실측 결과 동시 실행 슬롯·
tmux·토큰 예산 같은 진짜 한도 자원이 거의 없어서(대부분 무한 또는 표시 cap),
한도 게이지는 존재하지 않는 자원 압박을 그리는 거짓 신호가 된다. 그래서 여기서는
한도가 분명한 '현재량'만 막대로 보여주고, 라벨에 '현재량'을 명시해 오해를 막는다.

세 지표 (전부 기존 .project 데이터·세션 풀에서 결정적으로 나온다):
- 미소비 inbox  : 받은 편지함에 쌓인 미처리 메시지 총합(워커별 큐깊이의 합).
- active 세션   : headless 대화가 살아있는 워커 수(session_pool.active_workers).
- 미완 백로그   : 미리알림에서 아직 안 끝난 작업 수.

막대는 '한도 대비'가 아니라 '관측 스케일 대비' 채움이다(scale 인자). 절대 수치를
항상 크게 병기해 막대가 한도처럼 읽히지 않게 한다.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

BAR_WIDTH = 14


def _bar(value: int, scale: int) -> str:
    """value를 scale 대비 BAR_WIDTH 칸 막대로. scale은 한도가 아니라 표시 스케일."""
    scale = max(scale, 1)
    filled = min(BAR_WIDTH, round(BAR_WIDTH * value / scale))
    return "█" * filled + "░" * (BAR_WIDTH - filled)


class ResourceStrip(Horizontal):
    """팀 부하 현재량 — 한도 게이지가 아니라 현재 절대량 표시."""

    def compose(self) -> ComposeResult:
        # 세 칸을 가로로. 각 칸은 라벨 + 막대 + 절대수치.
        yield Static("(로딩…)", id="rs-inbox")
        yield Static("", id="rs-sessions")
        yield Static("", id="rs-backlog")

    def update_data(self, *, unread: int, active_sessions: int,
                    worker_count: int, open_backlog: int) -> None:
        # 표시 스케일: inbox는 워커 수의 ~3배(통상 큐깊이 상한 감각), 세션은 워커 수,
        # 백로그는 워커 수의 ~3배. 막대는 감각용이고 숫자가 정본임을 라벨로 못박는다.
        wc = max(worker_count, 1)
        self.query_one("#rs-inbox", Static).update(
            f"[b]미소비 inbox[/b] [dim](현재량)[/dim]\n"
            f"[red]{_bar(unread, wc * 3)}[/red] [b]{unread}[/b]")
        self.query_one("#rs-sessions", Static).update(
            f"[b]active 세션[/b] [dim](현재량)[/dim]\n"
            f"[green]{_bar(active_sessions, wc)}[/green] [b]{active_sessions}[/b]/[dim]{wc}[/dim]")
        self.query_one("#rs-backlog", Static).update(
            f"[b]미완 백로그[/b] [dim](현재량)[/dim]\n"
            f"[yellow]{_bar(open_backlog, wc * 3)}[/yellow] [b]{open_backlog}[/b]")
