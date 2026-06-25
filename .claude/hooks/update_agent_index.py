#!/usr/bin/env python3
"""Maintain the generated agent index in .claude/agents/agents.md."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


INDEX_HEADER = "## Files"
TABLE_HEADER = (
    "| Path | Role |\n"
    "| --- | --- |\n"
)


def project_root() -> Path:
    """Resolve the project root like the other hooks (cwd is unreliable here)."""
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return Path(str(raw)).expanduser().resolve()


def find_agents_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    return project_root() / ".claude/agents"


def project_root_for(agents_dir: Path) -> Path:
    if agents_dir.name == "agents" and agents_dir.parent.name == ".claude":
        return agents_dir.parent.parent
    return agents_dir.parent


def frontmatter_value(text: str, key: str) -> str:
    if not text.startswith("---"):
        return ""
    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip().strip("\"'") if match else ""


def display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return path.as_posix()


def collect_rows(agents_dir: Path) -> list[tuple[str, str]]:
    rows = [("`.claude/agents/agents.md`", "Human-readable index and maintenance note")]
    root = project_root_for(agents_dir)
    for path in sorted(agents_dir.glob("*.md")):
        if path.name == "agents.md" or path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        description = frontmatter_value(text, "description") or frontmatter_value(text, "name") or path.stem
        rows.append((f"`{display_path(path, root)}`", description))
    return rows


def render_index(rows: list[tuple[str, str]]) -> str:
    out = [INDEX_HEADER, "", TABLE_HEADER.rstrip("\n")]
    for path, role in rows:
        out.append(f"| {path} | {role} |")
    return "\n".join(out) + "\n"


def update_file(agents_md: Path, new_index: str) -> tuple[bool, str]:
    content = agents_md.read_text(encoding="utf-8")
    start = content.find(INDEX_HEADER)
    if start == -1:
        new_content = content.rstrip() + "\n\n" + new_index
        return new_content != content, new_content

    after = content[start + len(INDEX_HEADER):]
    boundary = re.search(r"^##\s+", after, re.MULTILINE)
    if boundary:
        end = start + len(INDEX_HEADER) + boundary.start()
        new_content = content[:start] + new_index + "\n" + content[end:].lstrip("\n")
    else:
        new_content = content[:start] + new_index
    return new_content != content, new_content


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maintain .claude/agents/agents.md")
    parser.add_argument("--agents-dir", default=None, help="Path to the agents directory")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Return exit code 1 without writing when the generated index is stale",
    )
    args = parser.parse_args(argv)

    agents_dir = find_agents_dir(args.agents_dir)
    agents_md = agents_dir / "agents.md"
    if not agents_md.exists():
        # Missing index is a contract failure under --check, but as a PostToolUse
        # hook it must never block an unrelated tool call, so exit 0 quietly.
        if args.check:
            print(f"error: {agents_md} does not exist", file=sys.stderr)
            return 1
        print(f"agent index not found at {agents_md}; skipping", file=sys.stderr)
        return 0

    rows = collect_rows(agents_dir)
    new_index = render_index(rows)
    changed, new_content = update_file(agents_md, new_index)

    if args.check:
        if changed:
            print("agent index is stale", file=sys.stderr)
            return 1
        print("agent index is current")
        return 0

    if changed:
        agents_md.write_text(new_content, encoding="utf-8")
        print(f"updated agent index: {len(rows) - 1} agent(s) -> {agents_md}")
    else:
        print("no changes; agent index is already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
