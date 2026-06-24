#!/usr/bin/env python3
"""Maintain the generated English skill index in skills.md.

The source skill documents can stay Korean. This script keeps the generated
index English by using stable skill slugs instead of copying Korean prose from
each SKILL.md file.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INDEX_HEADER = "## Skill Index"
LEGACY_INDEX_HEADERS = (INDEX_HEADER, "## 스킬 색인")
TABLE_HEADER = (
    "| Skill | Folder | Load rule |\n"
    "| --- | --- | --- |\n"
)


def find_skills_dir(explicit: str | None) -> Path:
    """Find the skills directory from an explicit path or this script location."""
    if explicit:
        return Path(explicit).resolve()
    return Path(__file__).resolve().parents[2]


def extract_name(text: str, fallback: str) -> str:
    m = re.search(r"^#\s*(?:스킬|Skill):\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def load_rule(name: str, folder: str) -> str:
    """Return an English rule without depending on Korean source prose."""
    return f"Open `{folder}/SKILL.md` only when the request clearly matches the `{name}` workflow."


def collect_rows(skills_dir: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for child in sorted(skills_dir.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(encoding="utf-8")
        name = extract_name(text, child.name)
        rows.append((name, f"`{child.name}/`", load_rule(name, child.name)))
    return rows


def render_index(rows: list[tuple[str, str, str]]) -> str:
    """Render the generated index section."""
    out = [INDEX_HEADER, "", TABLE_HEADER.rstrip("\n")]
    if rows:
        for name, folder, rule in rows:
            out.append(f"| {name} | {folder} | {rule} |")
    else:
        out.append("| _(none)_ | - | No skills are registered yet. |")
    return "\n".join(out) + "\n"


def update_file(skills_md: Path, new_index: str) -> tuple[bool, str]:
    """Replace only the generated index section in skills.md."""
    content = skills_md.read_text(encoding="utf-8")
    matches = [
        (content.find(header), header)
        for header in LEGACY_INDEX_HEADERS
        if content.find(header) != -1
    ]
    if not matches:
        new_content = content.rstrip() + "\n\n" + new_index
        return (new_content != content, new_content)

    start, found_header = min(matches, key=lambda item: item[0])
    after = content[start + len(found_header):]
    boundary = re.search(r"^(?:---\s*$|## )", after, re.MULTILINE)
    if boundary:
        end = start + len(found_header) + boundary.start()
        new_content = content[:start] + new_index + "\n" + content[end:]
    else:
        new_content = content[:start] + new_index
    return (new_content != content, new_content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maintain the generated skills.md index")
    parser.add_argument("--skills-dir", default=None, help="Path to the skills directory")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Return exit code 1 without writing when the generated index is stale",
    )
    args = parser.parse_args(argv)

    skills_dir = find_skills_dir(args.skills_dir)
    skills_md = skills_dir / "skills.md"
    if not skills_md.exists():
        print(f"error: {skills_md} does not exist", file=sys.stderr)
        return 2

    rows = collect_rows(skills_dir)
    new_index = render_index(rows)
    changed, new_content = update_file(skills_md, new_index)

    if args.check:
        if changed:
            print("skill index is stale", file=sys.stderr)
            return 1
        print("skill index is current")
        return 0

    if changed:
        skills_md.write_text(new_content, encoding="utf-8")
        print(f"updated skill index: {len(rows)} skill(s) -> {skills_md}")
    else:
        print("no changes; skill index is already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
