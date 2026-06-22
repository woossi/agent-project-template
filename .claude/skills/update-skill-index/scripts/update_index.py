#!/usr/bin/env python3
"""skills/ 를 스캔해 skills.md 의 '스킬 색인' 표를 재생성한다.

각 스킬 폴더의 SKILL.md 에서 다음을 읽는다.
  - 스킬 이름: 첫 줄의 `# 스킬: <이름>`
  - 한 줄 설명: `## 목적` 절의 첫 비어 있지 않은 줄

규칙:
  - skills/ 바로 아래의 디렉터리 중 SKILL.md 를 가진 것만 스킬로 본다.
  - `_` 로 시작하는 폴더(예: _template)는 본보기로 보고 색인에서 제외한다.
  - skills.md 의 '## 스킬 색인' 헤더부터 파일 끝까지를 새 표로 교체한다.

사용법:
  python scripts/update_index.py            # 기본 경로(저장소 루트 기준 skills/)
  python scripts/update_index.py --check     # 변경이 필요하면 종료코드 1 (CI/훅용)
  python scripts/update_index.py --skills-dir <경로>
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INDEX_HEADER = "## 스킬 색인"
TABLE_HEADER = (
    "| 스킬 | 폴더 | 한 줄 설명 |\n"
    "| --- | --- | --- |\n"
)


def find_skills_dir(explicit: str | None) -> Path:
    """skills 디렉터리를 찾는다. 명시값이 있으면 그것을, 없으면 이 스크립트 기준으로 추론."""
    if explicit:
        return Path(explicit).resolve()
    # 이 파일: skills/update-skill-index/scripts/update_index.py -> 부모의 부모의 부모가 skills/
    return Path(__file__).resolve().parents[2]


def extract_name(text: str, fallback: str) -> str:
    m = re.search(r"^#\s*스킬:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def extract_purpose(text: str) -> str:
    """`## 목적` 절의 첫 비어 있지 않은 줄을 반환."""
    m = re.search(r"^##\s*목적\s*$(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        line = line.strip()
        if line:
            return line
    return ""


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
        purpose = extract_purpose(text) or "(설명 없음 — SKILL.md의 ## 목적을 채우세요)"
        rows.append((name, f"`{child.name}/`", purpose))
    return rows


def render_index(rows: list[tuple[str, str, str]]) -> str:
    """'## 스킬 색인' 헤더 + 표 블록을 만든다 (뒤따르는 본문 섹션은 호출부에서 보존)."""
    out = [INDEX_HEADER, "", TABLE_HEADER.rstrip("\n")]
    if rows:
        for name, folder, purpose in rows:
            out.append(f"| {name} | {folder} | {purpose} |")
    else:
        out.append("| _(없음)_ | — | 아직 등록된 스킬이 없습니다. |")
    return "\n".join(out) + "\n"


def update_file(skills_md: Path, new_index: str) -> tuple[bool, str]:
    """skills.md 의 '## 스킬 색인' 섹션만 교체한다.

    교체 범위는 INDEX_HEADER 부터 다음 섹션 경계(수평선 `---` 또는 다음 `## `)
    직전까지. 색인 아래에 다른 본문(예: 스킬 작성 규칙)이 있어도 보존된다.
    반환: (변경여부, 새내용)
    """
    content = skills_md.read_text(encoding="utf-8")
    start = content.find(INDEX_HEADER)
    if start == -1:
        # 색인 헤더가 없으면 파일 끝에 추가
        new_content = content.rstrip() + "\n\n" + new_index
        return (new_content != content, new_content)

    # 색인 헤더 이후에서 다음 섹션 경계를 찾는다.
    after = content[start + len(INDEX_HEADER):]
    boundary = re.search(r"^(?:---\s*$|## )", after, re.MULTILINE)
    if boundary:
        end = start + len(INDEX_HEADER) + boundary.start()
        new_content = content[:start] + new_index + "\n" + content[end:]
    else:
        new_content = content[:start] + new_index
    return (new_content != content, new_content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="skills.md 색인 자동 갱신")
    parser.add_argument("--skills-dir", default=None, help="skills 디렉터리 경로")
    parser.add_argument(
        "--check",
        action="store_true",
        help="변경이 필요하면 파일을 쓰지 않고 종료코드 1 반환 (CI/훅용)",
    )
    args = parser.parse_args(argv)

    skills_dir = find_skills_dir(args.skills_dir)
    skills_md = skills_dir / "skills.md"
    if not skills_md.exists():
        print(f"오류: {skills_md} 를 찾을 수 없습니다.", file=sys.stderr)
        return 2

    rows = collect_rows(skills_dir)
    new_index = render_index(rows)
    changed, new_content = update_file(skills_md, new_index)

    if args.check:
        if changed:
            print("색인이 최신이 아닙니다. update_index.py 를 실행하세요.", file=sys.stderr)
            return 1
        print("색인 최신 상태 확인됨.")
        return 0

    if changed:
        skills_md.write_text(new_content, encoding="utf-8")
        print(f"색인 갱신: 스킬 {len(rows)}개 -> {skills_md}")
    else:
        print("변경 없음 (이미 최신).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
