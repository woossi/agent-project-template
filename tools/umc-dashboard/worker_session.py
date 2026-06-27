"""headless `claude` CLI를 자식 프로세스로 구동하는 워커 세션 (PoC / 백엔드).

지금까지 워커는 tmux 창 안의 대화형 claude였고, 출력이 창 안에만 있어 대시보드가
응답을 못 봤다. 여기서는 워커를 `claude --print --output-format stream-json` 자식
프로세스로 직접 띄운다 — 지시를 stdin/argv로 주고, 응답을 stdout JSON 스트림으로
직접 받는다. tmux도, 별도 API 키도 필요 없다(구독 인증 그대로, apiKeySource=none).

핵심:
- 워커별 cwd = teams/<팀>/<워커>/, 정체성 = env CLAUDE_AGENT_NAME=<워커>.
- 첫 턴은 session_id를 캡처하고, 이후 턴은 --resume <id>로 같은 대화를 잇는다.
- 권한: --permission-mode bypassPermissions. headless라 승인 프롬프트를 띄울 수
  없으므로 claude 내장 권한(ask)을 끈다. 이래도 안전한 이유 — 진짜 방어선은
  settings.json의 PreToolUse 가드 훅(guard_agent_workspace)이고, 이 훅은
  permission-mode와 무관하게 항상 실행되어 워크스페이스 격리(타팀 폴더/메일박스
  read 차단, deny_read 드롭오프 등)를 강제한다. (acceptEdits는 tasks.md 같은 일부
  경로를 여전히 ask로 떨궈 headless 워커가 영구 대기하던 문제가 있었다 — bypass로
  교정하고, 격리는 훅이 책임진다. ``--bare``만 훅을 끄므로 절대 쓰지 않는다.)
- trust: cwd가 ~/.claude.json에서 trust되지 않으면 .claude/settings.json의
  permissions.allow가 무시된다. ensure_trusted()로 1회 보장한다.

이 파일은 독립 실행 가능한 PoC다:
    python3 worker_session.py <worker> <team> "<지시>"
대시보드 통합은 이 위에 올린다(다음 단계).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    """위로 올라가며 .project/team.json 또는 AGENTS.md가 있는 디렉토리를 찾는다."""
    cur = (start or Path(__file__)).resolve()
    for d in [cur, *cur.parents]:
        if (d / ".project" / "team.json").exists() or (d / "AGENTS.md").exists():
            return d
    return Path.cwd()


def ensure_trusted(cwd: Path, *, claude_json: Path | None = None) -> bool:
    """cwd가 ~/.claude.json에서 trust되도록 보장한다(멱등). 새로 표시했으면 True.

    headless CLI는 trust되지 않은 워크스페이스의 permissions.allow를 무시하고
    경고를 낸다. 대화형으로 한 번 trust를 받는 대신 여기서 직접 표시한다 —
    워크스페이스 가드 훅이 어차피 경계를 강제하므로 안전하다.
    """
    p = claude_json or Path(os.path.expanduser("~/.claude.json"))
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        data = {}
    projects = data.setdefault("projects", {})
    key = str(cwd)
    entry = projects.setdefault(key, {})
    if entry.get("hasTrustDialogAccepted") is True:
        return False  # 이미 trust — 파일 미접촉(동시 호출 안전)
    entry["hasTrustDialogAccepted"] = True
    # 원자적 교체. tmp 파일명을 PID+uuid로 고유화한다 — 여러 워커를 동시에 구동하면
    # (2026-06-27 동시 지시) 고정 ``.claude.json.tmp``를 동시에 write·replace하다
    # FileNotFoundError 레이스가 났다. 고유명이면 각 스레드가 자기 tmp를 안전하게 쓴다.
    # (last-writer-wins: 동시에 서로 다른 워커를 trust 표시하면 한쪽 entry가 덮일 수
    #  있으나, 다음 호출이 비어 있으면 다시 표시하므로 수렴한다.)
    tmp = p.with_name(f"{p.name}.{os.getpid()}-{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        os.replace(tmp, p)
    except OSError:
        # 다른 스레드가 먼저 끝냈거나 일시적 충돌 — trust는 best-effort라 무시(다음 턴 재시도).
        try:
            tmp.unlink()
        except OSError:
            pass
        return False
    return True


@dataclass
class WorkerEvent:
    """stream-json 한 줄을 파싱한 이벤트 — 대시보드가 그릴 최소 형태."""
    kind: str            # "system" | "assistant" | "tool_use" | "result" | "error" | "raw"
    text: str = ""       # 사람이 읽을 한 줄
    raw: dict = field(default_factory=dict)


def _events_from_line(line: str) -> Iterator[WorkerEvent]:
    """stream-json 한 줄(JSON 객체)을 0개 이상의 WorkerEvent로 변환."""
    line = line.strip()
    if not line:
        return
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        yield WorkerEvent("raw", text=line[:200], raw={})
        return
    t = obj.get("type")
    if t == "system" and obj.get("subtype") == "init":
        sid = obj.get("session_id", "")
        yield WorkerEvent("system", text=f"세션 시작 {sid[:8]} (cwd={obj.get('cwd','')})", raw=obj)
    elif t == "assistant":
        for block in obj.get("message", {}).get("content", []):
            bt = block.get("type")
            if bt == "text" and block.get("text"):
                yield WorkerEvent("assistant", text=block["text"], raw=obj)
            elif bt == "tool_use":
                name = block.get("name", "?")
                yield WorkerEvent("tool_use", text=f"⚙ {name}", raw=obj)
    elif t == "result":
        sub = obj.get("subtype", "")
        cost = obj.get("total_cost_usd")
        cost_s = f" · ${cost:.4f}" if isinstance(cost, (int, float)) else ""
        yield WorkerEvent("result", text=f"완료({sub}){cost_s}", raw=obj)
    # 그 외(hook_started/response, rate_limit_event 등)는 조용히 무시.


@dataclass
class TurnResult:
    ok: bool
    session_id: str = ""
    text: str = ""          # assistant 텍스트 합본
    error: str = ""
    events: list[WorkerEvent] = field(default_factory=list)


class WorkerSession:
    """한 워커의 headless claude 세션. 턴마다 자식 프로세스를 띄우고 resume로 잇는다."""

    def __init__(self, worker: str, team: str, root: Path | None = None,
                 *, claude_cmd: str = "claude", permission_mode: str = "bypassPermissions"):
        self.worker = worker
        self.team = team
        self.root = root or repo_root()
        self.cwd = self.root / "teams" / team / worker
        self.claude_cmd = claude_cmd
        self.permission_mode = permission_mode
        self.session_id: str = ""

    def _env(self) -> dict:
        env = dict(os.environ)
        env["CLAUDE_AGENT_NAME"] = self.worker  # 정체성 주입 — main으로 붕괴 방지
        return env

    def _argv(self, prompt: str) -> list[str]:
        argv = [self.claude_cmd, "--print", prompt,
                "--output-format", "stream-json", "--verbose",
                "--permission-mode", self.permission_mode]
        if self.session_id:
            argv += ["--resume", self.session_id]
        return argv

    def send(self, prompt: str, *, on_event: Callable[[WorkerEvent], None] | None = None,
             timeout: float | None = None) -> TurnResult:
        """한 턴 실행: 지시를 보내고 응답 스트림을 파싱해 TurnResult로 돌려준다.

        on_event가 주어지면 줄이 도착할 때마다 호출한다(대시보드 라이브 표시용).
        """
        if not self.cwd.is_dir():
            return TurnResult(False, error=f"워커 폴더 없음: {self.cwd}")
        ensure_trusted(self.cwd)
        proc = subprocess.Popen(
            self._argv(prompt), cwd=str(self.cwd), env=self._env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        events: list[WorkerEvent] = []
        texts: list[str] = []
        sid = self.session_id
        assert proc.stdout is not None
        for line in proc.stdout:
            for ev in _events_from_line(line):
                events.append(ev)
                if ev.kind == "assistant":
                    texts.append(ev.text)
                # 첫 init/result에서 session_id를 잡는다(resume용).
                new_sid = ev.raw.get("session_id")
                if new_sid:
                    sid = new_sid
                if on_event:
                    on_event(ev)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            return TurnResult(False, session_id=sid, error="타임아웃", events=events)
        err = (proc.stderr.read() if proc.stderr else "").strip()
        if sid:
            self.session_id = sid
        ok = proc.returncode == 0
        return TurnResult(ok, session_id=sid, text="\n".join(texts),
                          error="" if ok else (err or f"exit {proc.returncode}"),
                          events=events)


def _cli() -> int:
    if len(sys.argv) < 4:
        print("usage: worker_session.py <worker> <team> '<지시>' [<후속 지시> ...]", file=sys.stderr)
        return 2
    worker, team = sys.argv[1], sys.argv[2]
    prompts = sys.argv[3:]
    sess = WorkerSession(worker, team)
    print(f"[워커 {worker} · 팀 {team} · cwd {sess.cwd}]")
    for i, prompt in enumerate(prompts, 1):
        print(f"\n── 턴 {i}: {prompt}")

        def show(ev: WorkerEvent) -> None:
            tag = {"assistant": "💬", "tool_use": "  ", "system": "▶", "result": "✓"}.get(ev.kind, "·")
            if ev.kind in ("assistant", "tool_use", "system", "result"):
                print(f"  {tag} {ev.text}")

        r = sess.send(prompt, on_event=show)
        if not r.ok:
            print(f"  [실패] {r.error}")
            return 1
        print(f"  [session_id={r.session_id[:8]} — 다음 턴은 이 세션을 resume]")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
