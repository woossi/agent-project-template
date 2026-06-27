#!/usr/bin/env python3
"""Claude Code hook guard for project-scoped agent workspace policy."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hooklib import project_dir_simple as project_dir  # noqa: E402


PATH_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "Grep", "Glob", "NotebookRead", "NotebookEdit"}
# Read vs write split (2026-06-27): drop-off slots (other teams' inbox) are write-OK but
# read-blocked, so the guard must know which a tool does. NotebookRead reads; NotebookEdit
# writes. Anything in PATH_TOOLS not listed as READ is treated as a writer (fail-safe: an
# unknown path tool is assumed to write, getting only the lenient plain-deny check — but it
# is still subject to the full deny list, so this never weakens isolation of deny paths).
READ_PATH_TOOLS = {"Read", "Grep", "Glob", "NotebookRead"}
# The write tools, derived as the complement of READ within PATH_TOOLS. A path on the
# ``deny_write`` list is blocked for these (and for Bash, which can write) but ALLOWED for
# read tools — the mirror image of ``deny_read``. Used to grant a read-only coordinator
# (orchestrator) read access to every worker folder while still forbidding it from writing
# a worker's deliverables (2026-06-28 user decision: "orchestrator만 전 워커 read-only").
WRITE_PATH_TOOLS = PATH_TOOLS - READ_PATH_TOOLS
DIRECT_PATH_KEYS = ("file_path", "path", "notebook_path")


def load_payload() -> dict[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_policy_path(raw_path: str | None, root: Path) -> Path | None:
    if not raw_path:
        raw_path = os.environ.get("CLAUDE_AGENT_WORKSPACE_POLICY")
    if not raw_path:
        default_path = root / ".claude/policies/agent-workspace.json"
        return default_path if default_path.exists() else None

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def load_policy(path: Path | None, explicit: bool) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.exists():
        if explicit:
            print(f"Agent workspace policy not found: {path}", file=sys.stderr)
            return {}
        return None
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid agent workspace policy JSON: {path}: {exc}", file=sys.stderr)
        return {}
    if not isinstance(policy, dict):
        print(f"Invalid agent workspace policy: root must be an object: {path}", file=sys.stderr)
        return {}
    return policy


def _load_subteam_members(root: Path) -> dict[str, list[str]] | None:
    """Parse .project/team.json subteams into {team_name: [member, ...]}.

    Single source of truth for which (team, worker) folder pairs are real. Returns
    None on any failure (missing file, bad JSON, unexpected shape) so the caller
    fail-safely abandons cwd-anchored identity and falls back to env/payload.
    """
    team_json = root / ".project" / "team.json"
    try:
        data = json.loads(team_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    subteams = data.get("subteams")
    if not isinstance(subteams, list):
        return None
    out: dict[str, list[str]] = {}
    for entry in subteams:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        members = entry.get("members")
        if isinstance(name, str) and name and isinstance(members, list):
            out[name] = [m for m in members if isinstance(m, str) and m]
    return out or None


# Sentinel: cwd is INSIDE teams/ but does not resolve to a registered worker
# folder (forged sibling folder, symlink mismatch, …). The caller must NOT fall
# back to the spoofable env identity in this case — it is fail-closed to a
# no-privilege identity so a worker cannot escape its sandbox by manufacturing an
# ambiguous cwd. Distinct from None (cwd outside teams/ → legit env fallback).
_CWD_FAILCLOSED = "\x00cwd-failclosed"


def _rel_worker(root: Path, cwd: Path) -> str | None:
    """If ``cwd`` (already a concrete Path) sits at/under teams/<team>/<worker>
    for a REAL member, return that worker; else None. No I/O beyond the caller's
    resolution choice — used twice (logical + physical) to detect symlink tricks."""
    try:
        rel = cwd.relative_to(root)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 3 or parts[0] != "teams":
        return None
    team, worker = parts[1], parts[2]
    members = _load_subteam_members(root)
    if members is None:
        return None
    if team in members and worker in members[team]:
        return worker
    return None


def _identity_from_cwd(root: Path, raw_cwd: str | None) -> str | None:
    """Derive identity from the real execution directory (cwd), not env.

    The worker runs claude from its own folder teams/<team>/<worker>/ (or a
    subdirectory). cwd is a hard-to-forge anchor, so when cwd lands inside a
    *registered* worker folder we adopt that worker as canonical and ignore any
    env/--as claim.

    Three outcomes:
      * a worker name  — cwd is a real worker folder; adopt it (ignore env).
      * None           — cwd is OUTSIDE teams/ entirely (root, orchestrator,
                         tests); caller keeps the env fallback.
      * _CWD_FAILCLOSED — cwd is INSIDE teams/ but does not map to a registered
                         worker (forged sibling folder like teams/data/fakelead,
                         or a symlink whose logical and physical targets disagree).
                         Caller must NOT trust env here — fail closed.

    Anti-forgery:
      * member check — <team>/<worker> must both be real per team.json, so a
        manufactured sibling folder name cannot mint an identity (it fails closed
        rather than falling through to env).
      * symlink check — we resolve cwd BOTH logically (no symlink following,
        os.path.normpath on the absolute path) and physically (Path.resolve,
        follows symlinks). A worker may only be adopted when BOTH agree on the
        same worker. A symlink inside one worker folder pointing at another
        worker yields a logical≠physical mismatch → fail closed (defeats the
        "ln -s ../data-lead leadlink && cd leadlink" escalation).
    """
    if not raw_cwd:
        return None

    expanded = Path(str(raw_cwd)).expanduser()
    # Make absolute against root WITHOUT following symlinks for the logical view.
    abs_cwd = expanded if expanded.is_absolute() else (root / expanded)
    logical = Path(os.path.normpath(str(abs_cwd)))
    physical = abs_cwd.resolve(strict=False)
    root_resolved = root.resolve(strict=False)

    # Is cwd within teams/ at all? Use the logical view (a symlink that escapes
    # teams/ logically but points back in must not be treated as "outside").
    inside_teams = False
    for base in (root, root_resolved):
        try:
            rel = logical.relative_to(base)
            if rel.parts and rel.parts[0] == "teams":
                inside_teams = True
                break
        except ValueError:
            continue
    # Also count the physical view landing in teams/ (symlink INTO teams/).
    if not inside_teams:
        try:
            rel = physical.relative_to(root_resolved)
            inside_teams = bool(rel.parts) and rel.parts[0] == "teams"
        except ValueError:
            inside_teams = False
    if not inside_teams:
        return None  # genuinely outside teams/ → legit env fallback

    # Inside teams/: require logical AND physical to name the SAME real worker.
    log_worker = _rel_worker(root, logical) or _rel_worker(root_resolved, logical)
    phys_worker = _rel_worker(root_resolved, physical) or _rel_worker(root, physical)
    if log_worker and phys_worker and log_worker == phys_worker:
        return log_worker
    # Inside teams/ but ambiguous/forged/symlinked → fail closed (no env trust).
    return _CWD_FAILCLOSED


def active_agent_name(payload: dict[str, Any], root: Path | None = None) -> str:
    # cwd-anchored identity takes priority over env (anti-forgery). Read the real
    # execution directory from payload.cwd (NOT project_dir(), which prefers
    # CLAUDE_PROJECT_DIR = root and would never reveal a worker subfolder).
    if root is not None:
        raw_cwd = payload.get("cwd") or os.getcwd()
        cwd_identity = _identity_from_cwd(root, raw_cwd)
        if cwd_identity == _CWD_FAILCLOSED:
            # cwd is inside teams/ but unresolvable to a real worker — deny env
            # trust. Return a no-privilege identity so no policy entry matches and
            # the strict fail-closed (unregistered-agent) path applies.
            return _CWD_FAILCLOSED
        if cwd_identity:
            return cwd_identity

    for key in ("CLAUDE_AGENT_NAME", "CLAUDE_SUBAGENT_NAME"):
        value = os.environ.get(key)
        if value:
            return value

    for key in ("agent_name", "subagent_name"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value

    agent = payload.get("agent")
    if isinstance(agent, str):
        return agent
    if isinstance(agent, dict):
        for key in ("name", "type"):
            value = agent.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def merged_config(policy: dict[str, Any], agent_name: str) -> dict[str, Any]:
    defaults = policy.get("defaults")
    if not isinstance(defaults, dict):
        defaults = {}

    agents = policy.get("agents")
    if not isinstance(agents, dict):
        agents = {}
    agent_config = agents.get(agent_name)
    registered = isinstance(agent_config, dict)
    if not registered:
        agent_config = {}

    allow = (
        as_string_list(agent_config.get("allow"))
        if "allow" in agent_config
        else as_string_list(defaults.get("allow")) or ["."]
    )
    deny = as_string_list(defaults.get("deny")) + as_string_list(agent_config.get("deny"))
    # deny_read: READ-only denial. A path here is blocked for Read tools but ALLOWED for
    # Write tools — a "drop-off slot". Used for other teams' inbox mailboxes so a worker can
    # POST to another team (write) but never READ that team's mail (no context bleed).
    deny_read = as_string_list(defaults.get("deny_read")) + as_string_list(agent_config.get("deny_read"))
    # deny_write: the mirror of deny_read. A path here is blocked for WRITE tools (Edit/Write/
    # MultiEdit/NotebookEdit/Bash) but ALLOWED for read tools — a "read-only window". Used to
    # let the orchestrator READ every worker folder while never WRITING a worker's output.
    deny_write = as_string_list(defaults.get("deny_write")) + as_string_list(agent_config.get("deny_write"))
    if not registered:
        # Unregistered / typo / empty / "main": synthesize a deny over EVERY registered
        # worker folder. With no agent entry of its own, no self-folder is exempted, so all
        # worker folders are blocked (fail-closed against identity collapse). The allow side
        # already falls back to defaults.allow (baseline-only), so no external team path leaks.
        # deny_read AND deny_write are folded into deny here: an unidentified caller gets the
        # STRICTEST rule (read AND write blocked), never a lenient one-sided exception.
        for cfg in agents.values():
            if isinstance(cfg, dict):
                deny += (as_string_list(cfg.get("deny")) + as_string_list(cfg.get("deny_read"))
                         + as_string_list(cfg.get("deny_write")))
        deny = sorted(set(deny))
        deny_read = []
        deny_write = []

    default_bash = defaults.get("bash")
    if not isinstance(default_bash, dict):
        default_bash = {}
    agent_bash = agent_config.get("bash")
    if not isinstance(agent_bash, dict):
        agent_bash = {}

    bash_allow = (
        as_string_list(agent_bash.get("allow"))
        if "allow" in agent_bash
        else as_string_list(default_bash.get("allow"))
    )
    bash_deny = as_string_list(default_bash.get("deny")) + as_string_list(agent_bash.get("deny"))
    bash_enabled = bool(agent_bash.get("enabled", default_bash.get("enabled", True)))

    return {
        "agent": agent_name or "main",
        "allow": allow,
        "deny": deny,
        "deny_read": deny_read,
        "deny_write": deny_write,
        "bash": {"allow": bash_allow, "deny": bash_deny, "enabled": bash_enabled},
    }


def iter_tool_paths(tool_input: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in DIRECT_PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    return paths


def relative_path(raw_path: str, root: Path) -> str | None:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        rel = candidate.resolve(strict=False).relative_to(root)
    except ValueError:
        return None
    return rel.as_posix() or "."


def path_targets(raw_path: str, root: Path) -> tuple[str | None, str]:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=False)
    try:
        rel = resolved.relative_to(root).as_posix() or "."
    except ValueError:
        rel = None
    return rel, resolved.as_posix()


def normalize_pattern(pattern: str, root: Path) -> str:
    path = Path(pattern).expanduser()
    if path.is_absolute():
        try:
            return path.resolve(strict=False).relative_to(root).as_posix()
        except ValueError:
            return path.resolve(strict=False).as_posix()
    normalized = pattern.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized or "."


def path_matches(pattern: str, rel_path: str, root: Path) -> bool:
    pattern = normalize_pattern(pattern, root)
    if pattern in {".", "**", "**/*"}:
        return True
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return rel_path == prefix or rel_path.startswith(prefix + "/")
    return rel_path == pattern or fnmatch.fnmatchcase(rel_path, pattern)


def path_matches_target(pattern: str, rel_path: str | None, abs_path: str, root: Path) -> bool:
    if rel_path is not None and path_matches(pattern, rel_path, root):
        return True
    if Path(pattern).expanduser().is_absolute():
        return path_matches(pattern, abs_path, root)
    return False


def command_matches(pattern: str, command: str) -> bool:
    return fnmatch.fnmatchcase(command, pattern)


def check_path_policy(paths: list[str], root: Path, config: dict[str, Any], *, is_read: bool = False) -> int:
    # Read tools also honor deny_read (read-only denial: drop-off slots are write-OK/read-NO).
    # Write tools instead honor deny_write (write-only denial: read-only windows are read-OK/
    # write-NO). The two extra lists are mutually exclusive by tool kind, so a path can be on
    # both and end up symmetrically read-AND-write blocked only when listed in plain deny.
    extra = config.get("deny_read", []) if is_read else config.get("deny_write", [])
    deny_patterns = config["deny"] + extra
    for raw_path in paths:
        rel, abs_path = path_targets(raw_path, root)
        display_path = rel if rel is not None else abs_path
        if any(path_matches_target(pattern, rel, abs_path, root) for pattern in deny_patterns):
            print(
                f"Blocked {display_path}: denied by workspace policy for agent {config['agent']}.",
                file=sys.stderr,
            )
            return 2
        if not any(path_matches_target(pattern, rel, abs_path, root) for pattern in config["allow"]):
            if rel is None:
                print(
                    f"Blocked {abs_path}: outside project root for agent {config['agent']}.",
                    file=sys.stderr,
                )
                return 2
            print(
                f"Blocked {display_path}: outside allowed workspace for agent {config['agent']}.",
                file=sys.stderr,
            )
            return 2
    return 0


def bash_path_tokens(command: str) -> list[str]:
    """Best-effort static extraction of path-like tokens from a Bash command.

    shlex-tokenize, then split each token further on = : , (to catch env=path,
    --flag=path, A:B / comma-joined PATH forms), strip redirect/pipe glyphs, and keep
    only fragments that contain a slash and do not start with '-'. Falls back to a naive
    split when shlex fails on unbalanced quotes (the fallback still surfaces peer paths).
    This is a deny-side guard only — it cannot catch paths hidden behind shell variables,
    globs, or here-docs, so it is a partial defense, not a complete one.
    """
    try:
        toks = shlex.split(command, comments=False, posix=True)
    except ValueError:
        toks = command.split()
    out: list[str] = []
    for tok in toks:
        for piece in re.split(r"[=:,]", tok):
            # Strip shell metacharacters/quotes/redirects that shlex may leave attached
            # to a path token (e.g. trailing ';' in "cat a.pdf; ls" or wrapping quotes).
            piece = piece.strip().strip("<>|&;()'\"`")
            if piece and "/" in piece and not piece.startswith("-"):
                out.append(piece)
    return out


def check_bash_path_targets(command: str, root: Path, config: dict[str, Any]) -> int:
    """Block a Bash command whose path-like arguments touch a DENIED path.

    Deny-only, mirroring ``check_path_policy``'s read-deny side onto Bash. Bash can read
    as easily as it can write (``cat``/``rg``/``ls``), so it must honor both plain ``deny``
    and ``deny_read``. This intentionally means direct shell writes into a drop-off inbox
    path are blocked; cross-team delivery should go through ``team_inbox.py post`` so no
    mailbox path is exposed as a shell token. Best-effort: static token extraction can't
    see shell variables, globs, or command substitution (see ``bash_path_tokens``); OS
    sandboxing is the hard backstop.

    ``deny_write`` is deliberately NOT applied to Bash: a read-only window (orchestrator over
    worker folders) must let the coordinator ``cat``/``rg``/``ls`` those paths from the shell.
    Bash tokens carry no static read/write intent (``cat`` vs ``rm`` look the same here), so
    enforcing deny_write would block the read it is meant to grant. The window is only ever
    handed to the trusted, non-adversarial coordinator; adversarial workers keep the strict
    plain-``deny``/``deny_read`` isolation, and the OS sandbox remains the hard backstop for
    any shell write.
    """
    deny = config["deny"] + config.get("deny_read", [])
    if not deny:
        return 0
    for tok in bash_path_tokens(command):
        rel, abs_path = path_targets(tok, root)
        if any(path_matches_target(pattern, rel, abs_path, root) for pattern in deny):
            display = rel if rel is not None else abs_path
            print(
                f"Blocked Bash command touching {display}: "
                f"denied by workspace policy for agent {config['agent']}.",
                file=sys.stderr,
            )
            return 2
    return 0


def check_bash_policy(command: str, root: Path, config: dict[str, Any]) -> int:
    bash = config["bash"]
    if not bash["enabled"]:
        print(f"Blocked Bash: disabled for agent {config['agent']}.", file=sys.stderr)
        return 2
    target_code = check_bash_path_targets(command, root, config)
    if target_code != 0:
        return target_code
    if any(command_matches(pattern, command) for pattern in bash["deny"]):
        print(
            f"Blocked Bash command: denied by workspace policy for agent {config['agent']}.",
            file=sys.stderr,
        )
        return 2
    if bash["allow"] and not any(command_matches(pattern, command) for pattern in bash["allow"]):
        print(
            f"Blocked Bash command: Bash command is not allowed for agent {config['agent']}.",
            file=sys.stderr,
        )
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", help="Path to agent workspace policy JSON")
    args = parser.parse_args(argv)

    payload = load_payload()
    root = project_dir(payload)
    explicit_policy = bool(args.policy or os.environ.get("CLAUDE_AGENT_WORKSPACE_POLICY"))
    policy_path = resolve_policy_path(args.policy, root)
    policy = load_policy(policy_path, explicit_policy)
    if policy is None:
        return 0
    if policy == {}:
        return 2

    if payload.get("hook_event_name") != "PreToolUse":
        return 0

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    config = merged_config(policy, active_agent_name(payload, root))

    if tool_name in PATH_TOOLS:
        is_read = tool_name in READ_PATH_TOOLS
        return check_path_policy(iter_tool_paths(tool_input), root, config, is_read=is_read)

    if tool_name == "Bash":
        command = tool_input.get("command")
        if isinstance(command, str):
            return check_bash_policy(command, root, config)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
