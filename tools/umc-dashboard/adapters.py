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

    def inbox_post(self, sender: str, to: list[str], subject: str, body: str,
                   *, reply_to: str | None = None) -> CliResult:
        argv = [self.python, self._inbox(), "post", "--as", sender,
                "--subject", subject, "--body", body]
        for r in to:
            argv += ["--to", r]
        if reply_to:
            argv += ["--reply-to", reply_to]
        return self._call_json(argv)

    def inbox_ack(self, agent: str, msg_id: str) -> CliResult:
        return self._call_json([self.python, self._inbox(), "ack", "--as", agent, "--id", msg_id])

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

    # ---------------- roster ----------------

    def agent_list(self) -> CliResult:
        return self._call_json([self.python, self._script("create-team-agent", "team_agent.py"), "list"])
