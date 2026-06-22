#!/usr/bin/env python3
"""용어 등록/검증 스크립트 (register-term 스킬의 실행 코드).

`.claude/memory/word.json` 의 `terms` 배열에 용어 항목을 안전하게 추가하거나,
사전 전체의 무결성(JSON 유효성·필수 필드·중복 term)을 점검한다.

이 스크립트는 비대화형이다. 사용자에게 "정의를 명확히 묻는" 일은 Claude(절차)가
수행하고, 이 스크립트는 받은 값을 검증하고 파일에 기록하는 일만 한다.

사용법:
  # 용어 추가 (4개 필드 권장: term/ko/definition/use_when)
  python scripts/register_term.py add \
      --term "RAG" --ko "검색 증강 생성" \
      --definition "외부 지식을 검색해 LLM 응답에 결합하는 기법" \
      --use-when "모델 지식만으로 부족해 출처가 필요한 답변을 만들 때"

  # 사전 무결성 점검만 (변경 없음; 문제가 있으면 종료코드 1)
  python scripts/register_term.py --check

옵션:
  --word-file <경로>   대상 word.json 경로 지정 (기본: 저장소 기준 .claude/memory/word.json)
  --allow-update       동일 term 이 이미 있으면 덮어쓰기(기본은 거부하고 종료코드 1)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 권장 필드 (AGENTS.md: term, ko, definition, use_when)
REQUIRED_FIELDS = ("term", "ko", "definition", "use_when")


def find_word_file(explicit: str | None) -> Path:
    """word.json 경로를 결정한다. 미지정 시 저장소 루트의 표준 위치를 쓴다."""
    if explicit:
        return Path(explicit).resolve()
    # 이 파일: .claude/skills/register-term/scripts/register_term.py
    # parents[0]=scripts, [1]=register-term, [2]=skills, [3]=.claude, [4]=저장소 루트
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / ".claude" / "memory" / "word.json"


def load_dict(path: Path) -> dict:
    """word.json 을 읽어 dict 로 반환. 형식이 어긋나면 ValueError."""
    if not path.exists():
        raise ValueError(f"word.json 을 찾을 수 없습니다: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"word.json 이 유효한 JSON 이 아닙니다: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("word.json 최상위는 객체(dict)여야 합니다.")
    if "terms" not in data:
        raise ValueError("word.json 에 'terms' 키가 없습니다.")
    if not isinstance(data["terms"], list):
        raise ValueError("'terms' 는 배열이어야 합니다.")
    return data


def validate_terms(terms: list) -> list[str]:
    """terms 배열 전체를 검증해 문제 목록을 반환한다(빈 목록이면 정상)."""
    problems: list[str] = []
    seen: dict[str, int] = {}
    for i, entry in enumerate(terms):
        if not isinstance(entry, dict):
            problems.append(f"[{i}] 항목이 객체가 아닙니다.")
            continue
        # 필수 필드 검사
        for field in REQUIRED_FIELDS:
            val = entry.get(field)
            if not isinstance(val, str) or not val.strip():
                problems.append(f"[{i}] 필드 '{field}' 가 비어 있거나 문자열이 아닙니다.")
        # 중복 term 검사 (대소문자 무시)
        term = entry.get("term")
        if isinstance(term, str) and term.strip():
            key = term.strip().lower()
            if key in seen:
                problems.append(
                    f"[{i}] term '{term}' 가 [{seen[key]}] 항목과 중복됩니다."
                )
            else:
                seen[key] = i
    return problems


def cmd_check(path: Path) -> int:
    data = load_dict(path)  # 형식 오류 시 예외 → main 에서 처리
    problems = validate_terms(data["terms"])
    if problems:
        print(f"✗ 무결성 점검 실패 ({path}):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"✓ 무결성 정상: {len(data['terms'])}개 용어 ({path})")
    return 0


def cmd_add(path: Path, entry: dict, allow_update: bool) -> int:
    data = load_dict(path)

    # 1) 추가하려는 항목 자체의 필수 필드 검증
    missing = [
        f for f in REQUIRED_FIELDS
        if not isinstance(entry.get(f), str) or not entry[f].strip()
    ]
    if missing:
        print(
            "✗ 필수 필드가 비어 있습니다: " + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "  4개 필드를 모두 채워야 합니다: " + ", ".join(REQUIRED_FIELDS),
            file=sys.stderr,
        )
        return 1

    # 값 정규화(앞뒤 공백 제거)
    entry = {f: entry[f].strip() for f in REQUIRED_FIELDS}
    key = entry["term"].lower()

    # 2) 기존 항목과 중복 검사
    terms = data["terms"]
    existing_idx = next(
        (i for i, e in enumerate(terms)
         if isinstance(e, dict)
         and isinstance(e.get("term"), str)
         and e["term"].strip().lower() == key),
        None,
    )
    if existing_idx is not None and not allow_update:
        print(
            f"✗ term '{entry['term']}' 는 이미 등록되어 있습니다(인덱스 {existing_idx}).",
            file=sys.stderr,
        )
        print(
            "  덮어쓰려면 --allow-update 를 사용하세요. (의도치 않은 변경 방지)",
            file=sys.stderr,
        )
        return 1

    if existing_idx is not None:
        terms[existing_idx] = entry
        action = "갱신"
    else:
        terms.append(entry)
        action = "추가"

    # 3) 추가 후 사전 전체 재검증 (안전망)
    problems = validate_terms(terms)
    if problems:
        print("✗ 추가 후 무결성 검증 실패(기록하지 않음):", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    # 4) 파일 기록 (한글 보존: ensure_ascii=False, 끝에 개행)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"✓ 용어 {action}: '{entry['term']}' → {path}")
    print(f"  현재 용어 수: {len(terms)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="word.json 용어 등록/검증",
    )
    p.add_argument("--word-file", default=None, help="대상 word.json 경로")
    p.add_argument(
        "--check",
        action="store_true",
        help="사전 무결성만 점검(추가하지 않음)",
    )
    p.add_argument("command", nargs="?", choices=["add"], help="add: 용어 추가")
    p.add_argument("--term", help="용어(원어/표기)")
    p.add_argument("--ko", help="한국어 표현")
    p.add_argument("--definition", help="정의")
    p.add_argument("--use-when", dest="use_when", help="사용 맥락")
    p.add_argument(
        "--allow-update",
        action="store_true",
        help="동일 term 이 있으면 덮어쓰기",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = find_word_file(args.word_file)

    try:
        if args.check:
            return cmd_check(path)
        if args.command == "add":
            entry = {
                "term": args.term or "",
                "ko": args.ko or "",
                "definition": args.definition or "",
                "use_when": args.use_when or "",
            }
            return cmd_add(path, entry, allow_update=args.allow_update)
        # 명령 없음
        print(
            "할 일을 지정하세요: 'add'(용어 추가) 또는 --check(점검).\n"
            "예: python scripts/register_term.py --check",
            file=sys.stderr,
        )
        return 2
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
