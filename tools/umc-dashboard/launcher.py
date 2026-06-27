"""tmux로 워커 Claude를 구동·조작 (Stage 2).

사용자는 이미 tmux 세션 안에서 대시보드를 띄운다. 워커를 같은 세션의 새 윈도우로
띄우면 Ctrl-b <숫자>로 워커↔대시보드를 오간다 — "터미널에서 다 관리".

핵심: 정체성 유실 방지. 새 윈도우에 ``export CLAUDE_AGENT_NAME=<이름>``을 박아
넣어 워커가 잘못된 정체성(main)으로 떨어지지 않게 한다.

tmux가 없거나 세션 밖이면 launch는 사유와 함께 실패를 반환한다(대시보드는 버튼 비활성).
runner 주입으로 테스트는 실제 tmux 미실행.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

Runner = Callable[[Sequence[str]], "tuple[int, str, str]"]


def _default_runner(argv: Sequence[str]) -> tuple[int, str, str]:
    p = subprocess.run(list(argv), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


@dataclass
class LaunchResult:
    ok: bool
    window: str = ""
    error: str = ""


# 사용자가 이미 운영 중인 tmux 윈도우 명명 규칙: ``UMC_<워커>``.
# 대시보드가 수동으로 띄운 워커도 같은 규칙으로 인식하도록 맞춘다.
WINDOW_PREFIX = "UMC_"


def _window_name(worker: str) -> str:
    return f"{WINDOW_PREFIX}{worker}"


class TmuxLauncher:
    """워커별 tmux 윈도우 생애주기. window 이름 = ``umc:<worker>``."""

    def __init__(self, root: Path, runner: Runner | None = None,
                 claude_cmd: str = "claude", in_tmux: bool | None = None):
        self.root = root
        self._run = runner or _default_runner
        self.claude_cmd = claude_cmd
        # 테스트는 in_tmux를 명시; 실런타임은 $TMUX로 판별
        self.in_tmux = bool(os.environ.get("TMUX")) if in_tmux is None else in_tmux

    def available(self) -> tuple[bool, str]:
        if shutil.which("tmux") is None:
            return False, "tmux 미설치"
        if not self.in_tmux:
            return False, "tmux 세션 밖 — 세션 안에서 대시보드를 실행하세요"
        return True, ""

    def worker_dir(self, worker: str, team: str) -> Path:
        return self.root / "teams" / team / worker

    def is_running(self, worker: str) -> bool:
        """그 워커의 윈도우가 떠 있는지(모든 세션 기준)."""
        return worker in self.running_workers()

    def launch(self, worker: str, team: str) -> LaunchResult:
        """새 윈도우에서 export CLAUDE_AGENT_NAME + cd + claude 실행."""
        ok, why = self.available()
        if not ok:
            return LaunchResult(False, error=why)
        if self.is_running(worker):
            return LaunchResult(True, window=_window_name(worker))  # 이미 떠 있음 — 멱등
        wdir = self.worker_dir(worker, team)
        if not wdir.is_dir():
            return LaunchResult(False, error=f"워커 폴더 없음: {wdir}")
        # 정체성을 박은 채 새 윈도우 생성. -d=백그라운드, -n=윈도우명, -c=시작 디렉토리.
        shell_cmd = f"export CLAUDE_AGENT_NAME={worker}; exec {self.claude_cmd}"
        rc, _out, err = self._run([
            "tmux", "new-window", "-d", "-n", _window_name(worker),
            "-c", str(wdir), shell_cmd,
        ])
        if rc != 0:
            return LaunchResult(False, error=err.strip() or "tmux new-window 실패")
        return LaunchResult(True, window=_window_name(worker))

    def send_message(self, worker: str, text: str) -> LaunchResult:
        """그 워커의 Claude 프롬프트에 텍스트를 입력하고 Enter(주입)."""
        ok, why = self.available()
        if not ok:
            return LaunchResult(False, error=why)
        if not self.is_running(worker):
            return LaunchResult(False, error="워커가 실행 중이 아님 — 먼저 구동")
        target = _window_name(worker)
        # literal(-l)로 텍스트, 그다음 Enter. 두 번 호출로 텍스트와 키 분리.
        rc, _o, err = self._run(["tmux", "send-keys", "-t", target, "-l", text])
        if rc != 0:
            return LaunchResult(False, error=err.strip() or "send-keys 실패")
        rc2, _o2, err2 = self._run(["tmux", "send-keys", "-t", target, "Enter"])
        if rc2 != 0:
            return LaunchResult(False, error=err2.strip() or "Enter 전송 실패")
        return LaunchResult(True, window=target)

    def interrupt(self, worker: str) -> LaunchResult:
        """그 워커에 Esc(중단) 전송 — Claude의 현재 생성/도구를 멈춘다."""
        ok, why = self.available()
        if not ok:
            return LaunchResult(False, error=why)
        if not self.is_running(worker):
            return LaunchResult(False, error="워커가 실행 중이 아님")
        target = _window_name(worker)
        rc, _o, err = self._run(["tmux", "send-keys", "-t", target, "Escape"])
        if rc != 0:
            return LaunchResult(False, error=err.strip() or "interrupt 실패")
        return LaunchResult(True, window=target)

    def focus(self, worker: str) -> LaunchResult:
        """그 워커 윈도우로 전환(select-window)."""
        ok, why = self.available()
        if not ok:
            return LaunchResult(False, error=why)
        if not self.is_running(worker):
            return LaunchResult(False, error="워커가 실행 중이 아님")
        target = _window_name(worker)
        rc, _o, err = self._run(["tmux", "select-window", "-t", target])
        if rc != 0:
            return LaunchResult(False, error=err.strip() or "select-window 실패")
        return LaunchResult(True, window=target)

    def running_workers(self) -> set[str]:
        """현재 떠 있는 모든 워커 이름 집합(상태배지용)."""
        ok, _ = self.available()
        if not ok:
            return set()
        # 모든 세션의 윈도우를 본다(-a) — 대시보드와 워커가 다른 세션/윈도우에 있을 수 있다.
        rc, out, _ = self._run(["tmux", "list-windows", "-a", "-F", "#{window_name}"])
        if rc != 0:
            return set()
        return {ln[len(WINDOW_PREFIX):] for ln in out.splitlines() if ln.startswith(WINDOW_PREFIX)}
