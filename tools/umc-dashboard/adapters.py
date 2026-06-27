"""Thin subprocess wrappers around the VERIFIED team CLIs.

The dashboard never re-implements team logic. Every write (and the Reminders read,
which needs osascript) goes through the existing scripts:

    reminders_bridge.py   Apple Reminders <-> team backlog
    team_inbox.py         peer message bus
    detect_promotions.py  / detect_derivations.py   resolve promotion/derivation
    team_agent.py         roster <-> folder reconciliation

Stage 0 uses only the read paths (reminders pull, agent list). Stage 1 adds the
write paths. A ``runner`` is injectable so tests can drive these without touching
the real Reminders DB or store.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

SKILLS = ".claude/skills"

# A runner takes argv + cwd and returns (returncode, stdout, stderr).
Runner = Callable[[Sequence[str], Path], "tuple[int, str, str]"]


def _default_runner(argv: Sequence[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(list(argv), cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


@dataclass
class CliResult:
    ok: bool
    data: Any = None
    error: str = ""
    raw: str = ""


class TeamCli:
    """All team-CLI calls funnel through here. Inject a runner for tests."""

    def __init__(self, root: Path, runner: Runner | None = None, python: str = "python3"):
        self.root = root
        self.python = python
        self._run = runner or _default_runner

    def _script(self, skill: str, name: str) -> str:
        return str(self.root / SKILLS / skill / "scripts" / name)

    def _call_json(self, argv: Sequence[str]) -> CliResult:
        """Run a CLI that prints a one-line JSON envelope ({ok, ...})."""
        rc, out, err = self._run(argv, self.root)
        out = out.strip()
        if not out:
            return CliResult(ok=(rc == 0), error=err.strip(), raw=out)
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            return CliResult(ok=(rc == 0), error=err.strip() or "non-JSON output", raw=out)
        if isinstance(payload, dict) and "ok" in payload:
            return CliResult(
                ok=bool(payload.get("ok")),
                data=payload.get("result"),
                error=str(payload.get("error", "")),
                raw=out,
            )
        return CliResult(ok=(rc == 0), data=payload, raw=out)

    # ---------------- Reminders (read in stage 0, write in stage 1) ----------------

    def _reminders(self) -> str:
        return self._script("reminders-team-bridge", "reminders_bridge.py")

    def reminders_list_teams(self) -> CliResult:
        return self._call_json([self.python, self._reminders(), "list-teams"])

    def reminders_pull(self, team: str, *, include_done: bool = False) -> CliResult:
        argv = [self.python, self._reminders(), "pull", team]
        if include_done:
            argv.append("--all")
        return self._call_json(argv)

    def reminders_add(self, team: str, title: str, *, notes: str | None = None,
                      priority: int | None = None, due: str | None = None) -> CliResult:
        argv = [self.python, self._reminders(), "add", team, title]
        if notes:
            argv += ["--notes", notes]
        if priority is not None:
            argv += ["--priority", str(priority)]
        if due:
            argv += ["--due", due]
        return self._call_json(argv)

    def reminders_complete(self, team: str, reminder_id: str) -> CliResult:
        return self._call_json([self.python, self._reminders(), "complete", team, "--id", reminder_id])

    def reminders_annotate(self, team: str, note: str, reminder_id: str) -> CliResult:
        return self._call_json([self.python, self._reminders(), "annotate", team, note, "--id", reminder_id])

    # ---------------- inbox (peer message bus) ----------------

    def _inbox(self) -> str:
        return self._script("team-inbox", "team_inbox.py")

    def inbox_post(self, sender: str, to_team: str, subject: str, body: str,
                   *, reply_to: str | None = None,
                   quality_gate: dict | None = None, verdict: dict | None = None,
                   work_ref: str | None = None) -> CliResult:
        # 팀 전용 단일 채널(2026-06-27): 모든 발행은 --to-team. 개인 주소·broadcast 폐지.
        argv = [self.python, self._inbox(), "post", "--from", sender,
                "--to-team", to_team, "--subject", subject, "--body", body]
        if reply_to:
            argv += ["--reply-to", reply_to]
        # (가) 품질 루프 필드: 할당 시 quality_gate, 검수 회신 시 verdict+work_ref.
        if quality_gate is not None:
            argv += ["--quality-gate", json.dumps(quality_gate, ensure_ascii=False)]
        if verdict is not None:
            argv += ["--verdict", json.dumps(verdict, ensure_ascii=False)]
        if work_ref:
            argv += ["--work-ref", work_ref]
        return self._call_json(argv)

    def inbox_ack(self, team: str, msg_id: str, agent: str) -> CliResult:
        """claim한 팀 메시지를 처리완료. 팀 전용 모델이라 --team 필수."""
        return self._call_json([self.python, self._inbox(), "ack",
                                "--team", team, "--as", agent, "--id", msg_id])

    def inbox_claim(self, team: str, msg_id: str, claimer: str) -> CliResult:
        """팀 메일박스 메시지를 워커가 claim(원자적). 경합 시 1명만 성공."""
        return self._call_json([self.python, self._inbox(), "claim",
                                "--team", team, "--id", msg_id, "--as", claimer])

    def inbox_read_team(self, team: str, *, all_states: bool = False) -> CliResult:
        """팀 메일박스 읽기(미claim, --all이면 claimed+consumed 포함)."""
        argv = [self.python, self._inbox(), "read", "--team", team]
        if all_states:
            argv.append("--all")
        return self._call_json(argv)

    # ---------------- promotion / derivation resolve ----------------

    def resolve_promotion(self, kind: str, key: str, decision: str, reason: str = "") -> CliResult:
        argv = [self.python, str(self.root / ".claude/hooks/detect_promotions.py"),
                "resolve", "--kind", kind, "--key", key, "--decision", decision]
        if reason:
            argv += ["--reason", reason]
        return self._call_json(argv)

    def resolve_derivation(self, kind: str, key: str, decision: str, reason: str = "") -> CliResult:
        argv = [self.python, str(self.root / ".claude/hooks/detect_derivations.py"),
                "resolve", "--kind", kind, "--key", key, "--decision", decision]
        if reason:
            argv += ["--reason", reason]
        return self._call_json(argv)

    # ---------------- quality ledger ((가)+(나) 품질 루프) ----------------

    def _quality_ledger(self) -> str:
        return self._script("team-quality-ledger", "quality_ledger.py")

    def quality_record(self, team: str, worker: str, kind: str, result: str,
                       *, work_ref: str | None = None, by: str | None = None,
                       round_: str | None = None) -> CliResult:
        """검증팀 verdict를 팀장 quality-ledger에 기록(PASS만 통과, PARTIAL/FAIL=실패)."""
        argv = [self.python, self._quality_ledger(), "--team", team, "record",
                "--worker", worker, "--kind", kind, "--result", result]
        if work_ref:
            argv += ["--work-ref", work_ref]
        if by:
            argv += ["--by", by]
        if round_:
            argv += ["--round", round_]
        return self._call_json(argv)

    def quality_signal(self, team: str, *, threshold: int = 2) -> CliResult:
        """(나) 2연속 실패 신호: spawn_specialized_worker / rebalance 권고."""
        return self._call_json([self.python, self._quality_ledger(), "--team", team,
                                "signal", "--threshold", str(threshold)])

    def quality_mark_spawned(self, team: str, worker: str, kind: str) -> CliResult:
        return self._call_json([self.python, self._quality_ledger(), "--team", team,
                                "mark-spawned", "--worker", worker, "--kind", kind])

    # ---------------- roster ----------------

    def agent_list(self) -> CliResult:
        return self._call_json([self.python, self._script("create-team-agent", "team_agent.py"), "list"])

    def agent_create(self, name: str, subteam: str, requester: str,
                     *, role: str | None = None) -> CliResult:
        """(나)→(다): 팀장이 자기 팀에 전문화 워커 생성. own-team 가드가 적용된다."""
        argv = [self.python, self._script("create-team-agent", "team_agent.py"), "create", name,
                "--subteam", subteam, "--requester", requester]
        if role:
            argv += ["--role", role]
        return self._call_json(argv)
