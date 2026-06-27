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
import os
import sys
from pathlib import Path

# 권장 필드 (AGENTS.md: term, ko, definition, use_when)
REQUIRED_FIELDS = ("term", "ko", "definition", "use_when")


def repo_root_of() -> Path:
    """이 스크립트 기준 저장소 루트를 반환한다."""
    # 이 파일: .claude/skills/register-term/scripts/register_term.py
    # parents[0]=scripts, [1]=register-term, [2]=skills, [3]=.claude, [4]=저장소 루트
    return Path(__file__).resolve().parents[4]


def find_word_file(explicit: str | None) -> Path:
    """word.json 경로를 결정한다. 미지정 시 저장소 루트의 표준 위치를 쓴다."""
    if explicit:
        return Path(explicit).resolve()
    return repo_root_of() / ".claude" / "memory" / "word.json"


def owner_set(repo_root: Path) -> set[str]:
    """공유 메모리 쓰기 권한을 가진 owner 집합을 구성한다.

    구성요소:
    - team-promotion.json governance.company_owner / authoring_owner
    - team.json subteams[*].orchestrator (모든 팀장)
    """
    owners: set[str] = set()
    promo = repo_root / ".project" / "policies" / "team-promotion.json"
    try:
        gov = json.loads(promo.read_text(encoding="utf-8")).get("governance", {})
        for key in ("company_owner", "authoring_owner"):
            val = gov.get(key)
            if isinstance(val, str) and val.strip():
                owners.add(val.strip())
    except (OSError, json.JSONDecodeError):
        pass
    team = repo_root / ".project" / "team.json"
    try:
        subteams = json.loads(team.read_text(encoding="utf-8")).get("subteams", [])
        for st in subteams if isinstance(subteams, list) else []:
            orch = st.get("orchestrator") if isinstance(st, dict) else None
            if isinstance(orch, str) and orch.strip():
                owners.add(orch.strip())
    except (OSError, json.JSONDecodeError):
        pass
    return owners


def _subteams_map(repo_root: Path) -> dict[str, list[str]]:
    """team.json subteams 를 {팀: [멤버]} 로 읽는다(단일 출처)."""
    out: dict[str, list[str]] = {}
    team = repo_root / ".project" / "team.json"
    try:
        subteams = json.loads(team.read_text(encoding="utf-8")).get("subteams", [])
    except (OSError, json.JSONDecodeError):
        return out
    for st in subteams if isinstance(subteams, list) else []:
        if isinstance(st, dict) and isinstance(st.get("name"), str):
            out[st["name"]] = [m for m in (st.get("members") or []) if isinstance(m, str)]
    return out


# Sentinel: cwd is INSIDE teams/ but unresolvable to a real worker (forged sibling
# folder, or symlink with logical/physical mismatch). Identity fails closed to this
# no-privilege name so the owner gate (_is_owner) rejects it — never trust env here.
CWD_FAILCLOSED = "__cwd_failclosed__"


def _worker_at(repo_root: Path, candidate: Path) -> str | None:
    """candidate(구체 Path)가 teams/<팀>/<워커>(실제 멤버) 위치면 <워커> 반환, 아니면 None.
    순수 경로 판정(해석 없음) — 호출자가 logical/physical을 따로 넘겨 심링크 우회를 잡는다."""
    try:
        rel = candidate.relative_to(repo_root)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 3 or parts[0] != "teams":
        return None
    team, worker = parts[1], parts[2]
    members = _subteams_map(repo_root).get(team)
    if members is None or worker not in members:
        return None
    return worker


def _identity_from_cwd(repo_root: Path, cwd: Path | None = None):
    """실행 cwd 에서 정체성을 역도출한다(위조-어려운 앵커, guard·team_inbox 와 동일 규칙).

    반환: 워커 이름 / None(cwd 가 teams/ 밖 → env·--as 폴백 정당) /
    CWD_FAILCLOSED(cwd 가 teams/ 안인데 미해석 → env 신뢰 거부, owner 게이트가 차단).

    위조 방어 2겹:
      * 멤버 검증 — <팀>/<워커> 둘 다 team.json 의 실제값이어야 한다. 가짜 시블링
        폴더(teams/data/fakelead)는 정체성을 못 만들고, teams/ 안이므로 fail-closed.
      * 심링크 — cwd 를 logical(심링크 비추종)·physical(resolve, 추종) 둘 다 보고,
        같은 워커로 일치할 때만 채택. 워커 폴더 안에 다른 워커를 가리키는 심링크
        (ln -s ../data-lead leadlink && cd leadlink)는 logical≠physical → fail-closed.

    CLAUDE_PROJECT_DIR(항상 루트) 미사용. 심링크 방어 핵심: os.getcwd()는 physical
    경로만 반환(커널이 chdir 시 심링크를 이미 해석)하므로, logical 뷰는 셸의 $PWD
    (cd로 통과한 심링크 경로를 보존)에서, physical 뷰는 os.getcwd()에서 따로 취한다.
    둘 다 같은 실제 워커여야 채택 — 'cd 심링크' 승격을 막는다.
    """
    if cwd is not None:
        log_raw = phys_raw = cwd
    else:
        pwd_env = os.environ.get("PWD")
        log_raw = Path(pwd_env) if pwd_env else Path.cwd()
        phys_raw = Path.cwd()
    log_raw = log_raw if log_raw.is_absolute() else (repo_root / log_raw)
    phys_raw = phys_raw if phys_raw.is_absolute() else (repo_root / phys_raw)
    logical = Path(os.path.normpath(str(log_raw)))
    physical = phys_raw.resolve()
    root_res = repo_root.resolve()

    inside = False
    for base in (repo_root, root_res):
        try:
            rel = logical.relative_to(base)
            if rel.parts and rel.parts[0] == "teams":
                inside = True
                break
        except ValueError:
            continue
    if not inside:
        try:
            rel = physical.relative_to(root_res)
            inside = bool(rel.parts) and rel.parts[0] == "teams"
        except ValueError:
            inside = False
    if not inside:
        return None

    log_w = _worker_at(repo_root, logical) or _worker_at(root_res, logical)
    phys_w = _worker_at(root_res, physical) or _worker_at(repo_root, physical)
    if log_w and phys_w and log_w == phys_w:
        return log_w
    return CWD_FAILCLOSED


def _is_owner(repo_root: Path, identity: str | None) -> bool:
    """identity 가 공유 메모리 쓰기 owner 집합에 속하는지 판정한다."""
    if not identity:
        return False
    return identity in owner_set(repo_root)


def is_shared_target(path: Path, repo_root: Path) -> bool:
    """대상 word.json 이 공유 경로(.project/ 또는 루트 .claude/memory/)인지 판정한다.

    워커 개인폴더(teams/<팀>/<워커>/.claude/memory/...)는 공유가 아니다.
    """
    try:
        rel = path.resolve().relative_to(repo_root)
    except ValueError:
        # 저장소 밖 경로는 공유 대상으로 보지 않는다(개인/외부).
        return False
    parts = rel.parts
    if not parts:
        return False
    # 루트 .claude/memory/ (워커 폴더 teams/.../.claude/memory 는 제외)
    if parts[0] == ".claude" and len(parts) >= 2 and parts[1] == "memory":
        return True
    # .project/ 공유 store
    if parts[0] == ".project":
        return True
    return False


SHARED_DENY_MSG = (
    "✗ 공유 용어 사전은 팀장/orchestrator만 등록 가능. "
    "워커는 자기 폴더 word.json에만 등록하거나 팀장에게 보고하세요."
)


def gate_shared_write(path: Path, repo_root: Path, identity: str | None) -> int | None:
    """공유 word.json 쓰기 전 owner 게이트. 차단이면 종료코드 1, 통과면 None."""
    if not is_shared_target(path, repo_root):
        return None  # 워커 개인폴더 등 비공유 타깃은 게이트 통과(private 자유).
    if not _is_owner(repo_root, identity):
        print(SHARED_DENY_MSG, file=sys.stderr)
        return 1
    return None


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
        "--as",
        dest="as_identity",
        default=None,
        help="정체성 명시(기본: $CLAUDE_AGENT_NAME). 공유 사전 게이트 판정에 쓴다.",
    )
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
    repo_root = repo_root_of()
    # cwd 앵커드 정체성: 워커가 --as/CLAUDE_AGENT_NAME 로 owner 를 위조해도, 실행 cwd 가
    # 자기 워커 폴더면 그 워커를 정본으로 채택해 owner 게이트가 비-owner 로 거부한다.
    # cwd 가 워커 폴더 밖이면(orchestrator 루트·테스트) 기존 --as/env 폴백 100% 보존.
    cwd_identity = _identity_from_cwd(repo_root)
    identity = cwd_identity or args.as_identity or os.environ.get("CLAUDE_AGENT_NAME")

    try:
        if args.check:
            return cmd_check(path)
        if args.command == "add":
            # 공유 word.json(.project/ · 루트 .claude/memory/) 쓰기는 owner 게이트.
            # 정체성 미설정 + 공유 타깃이면 owner 아님 → 거부(우회 방지).
            gated = gate_shared_write(path, repo_root, identity)
            if gated is not None:
                return gated
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
