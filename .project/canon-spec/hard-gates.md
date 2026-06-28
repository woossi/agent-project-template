# Canon hard gates

상태: 2026-06-28 Rust `canon-enforce` 기준.

## 실행 계층

- 런타임 enforce: `crates/canon-enforce` Rust CLI
- 호환 wrapper: `.claude/hooks/canon_integrity.py`
- hook 등록: `.claude/settings.json`의 `Edit|Write|MultiEdit|NotebookEdit|Bash`
- 검증 명령: `python3 .claude/hooks/canon_integrity.py check --project-root .`

Python wrapper는 빌드된 `target/debug/canon-enforce`가 있으면 그 바이너리를 호출하고, 없으면 `cargo run --quiet -p canon-enforce -- ...`로 Rust enforce를 실행한다. Cargo가 없을 때만 Python fallback을 사용한다.

## Hard-gate 지표

| 코드 | 차단 조건 | 구현 위치 |
| --- | --- | --- |
| `E_DUP_ID` | 같은 kind 내부 ID 중복 | Rust `file_ids`, Python duplicate pass |
| `E_SCHEMA_REQUIRED` | evidence 필수 필드 누락 또는 ID prefix 불일치 | `.project/schema/evidence.schema.json`, Rust/Python record shape |
| `E_DANGLING_LINK` | claim/evidence/provenance/lit_prop/risk 링크 대상 없음 | Rust/Python generic link pass |
| `E_DEPRECATED_REF` | active record가 deprecated/replaced target 참조 | Rust/Python generic link pass |
| `E_LINK_TYPE` | 링크 필드가 list가 아님 | Rust/Python generic link pass |
| `E_SUPERSEDES_DANGLING` | `supersedes` 대상 없음 또는 self-supersedes | Rust/Python supersedes pass |
| `E_RELATION_DANGLING` | claim relation 대상 없음 | Rust/Python relation pass |
| `E_RELATION_TYPE` | relation type이 허용 집합 밖 | Rust/Python relation pass |
| `E_RELATION_CYCLE` | `depends_on` claim relation cycle | Rust/Python relation DAG pass |
| `E_BIBKEY` | lit_prop bibkey 누락 또는 refs.bib에 없음 | Rust/Python bibkey pass |
| `E_OWNER_APPROVAL` | canon owner가 아닌 actor가 `.project` canon record write 시도 | Rust/Python guard |

## Warning 지표

| 코드 | 경고 조건 | 비고 |
| --- | --- | --- |
| `W_ORPHAN` | active evidence/provenance가 아무 record에서도 참조되지 않음 | manuscript에서 미사용 가능성 |
| `W_SUPERSEDES_ACTIVE` | supersedes 대상이 아직 active | predecessor retire 필요 |
| `W_UNWIRED_RUN` | provenance.run_id 대상 runs 없음 | placeholder/migration 확인 |
| `W_UNWIRED_DATA` | provenance.source_data 대상 data_registry 없음 | placeholder/migration 확인 |
| `W_BIBKEY_UNVERIFIED` | refs.bib를 읽을 수 없어 bibkey 확인 불가 | 격리 환경 warning |
| `W_CLARITY` | clarity R8/R9/R10 어휘감사 hit | 판단은 writer/reviewer |

## 범위

Hard gate는 구조와 승인만 차단한다. Claim 내용, evidence 내용, evidence 간 새 내용 합성은 만들지 않는다. Evidence 간 결정론은 `derived_from`이나 provenance 링크 같은 구조 관계에 한정한다.
