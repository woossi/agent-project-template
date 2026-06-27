"""launcher.py 테스트 — 가짜 runner, 실제 tmux 미실행. CI-safe."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from launcher import TmuxLauncher  # noqa: E402


class FakeTmux:
    """tmux 윈도우 상태를 메모리로 흉내낸다."""
    def __init__(self):
        self.windows: set[str] = set()
        self.calls: list[list[str]] = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        if "new-window" in argv:
            self.windows.add(argv[argv.index("-n") + 1])
            return 0, "", ""
        if "list-windows" in argv:
            return 0, "\n".join(self.windows), ""
        return 0, "", ""


def _L(root="/repo", **kw):
    fake = FakeTmux()
    return TmuxLauncher(Path(root), runner=fake, in_tmux=True, **kw), fake


def test_unavailable_outside_tmux():
    L = TmuxLauncher(Path("/repo"), runner=lambda a: (0, "", ""), in_tmux=False)
    ok, why = L.available()
    assert not ok and "세션 밖" in why


def test_launch_creates_window_with_identity(tmp_path):
    # 워커 폴더 존재해야 launch 성공
    wdir = tmp_path / "teams" / "scout" / "paper-scout"
    wdir.mkdir(parents=True)
    fake = FakeTmux()
    L = TmuxLauncher(tmp_path, runner=fake, in_tmux=True)
    r = L.launch("paper-scout", "scout")
    assert r.ok and r.window == "UMC_paper-scout"
    # 정체성이 명령에 박혔는지
    nw = next(c for c in fake.calls if "new-window" in c)
    assert any("CLAUDE_AGENT_NAME=paper-scout" in part for part in nw)
    # running_workers는 umc: 접두어를 떼고 워커 이름만 (AgentGrid가 이름으로 매칭)
    assert "paper-scout" in L.running_workers()
    assert L.is_running("paper-scout")


def test_launch_idempotent(tmp_path):
    wdir = tmp_path / "teams" / "scout" / "paper-scout"
    wdir.mkdir(parents=True)
    fake = FakeTmux()
    L = TmuxLauncher(tmp_path, runner=fake, in_tmux=True)
    L.launch("paper-scout", "scout")
    n1 = sum(1 for c in fake.calls if "new-window" in c)
    L.launch("paper-scout", "scout")  # 이미 떠 있음
    n2 = sum(1 for c in fake.calls if "new-window" in c)
    assert n1 == n2 == 1  # 두 번째는 윈도우를 새로 안 만듦


def test_launch_missing_folder_fails(tmp_path):
    fake = FakeTmux()
    L = TmuxLauncher(tmp_path, runner=fake, in_tmux=True)
    r = L.launch("ghost", "nope")
    assert not r.ok and "폴더 없음" in r.error


def test_send_message_requires_running():
    L, fake = _L()
    r = L.send_message("paper-scout", "hi")  # 안 떠 있음
    assert not r.ok and "실행 중이 아님" in r.error


def test_send_message_literal_then_enter(tmp_path):
    wdir = tmp_path / "teams" / "scout" / "paper-scout"
    wdir.mkdir(parents=True)
    fake = FakeTmux()
    L = TmuxLauncher(tmp_path, runner=fake, in_tmux=True)
    L.launch("paper-scout", "scout")
    r = L.send_message("paper-scout", "안녕")
    assert r.ok
    sends = [c for c in fake.calls if "send-keys" in c]
    assert any("-l" in c and "안녕" in c for c in sends)
    assert any("Enter" in c for c in sends)


def test_interrupt_sends_escape(tmp_path):
    wdir = tmp_path / "teams" / "scout" / "paper-scout"
    wdir.mkdir(parents=True)
    fake = FakeTmux()
    L = TmuxLauncher(tmp_path, runner=fake, in_tmux=True)
    L.launch("paper-scout", "scout")
    r = L.interrupt("paper-scout")
    assert r.ok
    assert any("send-keys" in c and "Escape" in c for c in fake.calls)
