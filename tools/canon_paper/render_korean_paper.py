#!/usr/bin/env python3
"""Render the deterministic canon skeleton into a Korean academic PDF.

The renderer does not invent claims or evidence. It reads existing canon JSON,
orders claims deterministically, attaches evidence as footnotes, writes a Markdown
skeleton, and delegates PDF creation to pandoc/xelatex.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _load_dir(path: Path, id_field: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.is_dir():
        return records
    for file in sorted(path.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        rid = data.get(id_field)
        if isinstance(rid, str) and rid:
            records[rid] = data
    return records


def _claim_order(claims: dict[str, dict[str, Any]]) -> list[str]:
    deps: dict[str, set[str]] = {cid: set() for cid in claims}
    for cid, claim in claims.items():
        for rel in claim.get("relations") or []:
            if not isinstance(rel, dict):
                continue
            if rel.get("type") == "depends_on" and rel.get("target") in claims:
                deps[cid].add(str(rel["target"]))

    ordered: list[str] = []
    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(cid: str) -> None:
        if cid in permanent:
            return
        if cid in temporary:
            raise ValueError(f"claim relation cycle at {cid}")
        temporary.add(cid)
        for dep in sorted(deps.get(cid, ())):
            visit(dep)
        temporary.remove(cid)
        permanent.add(cid)
        ordered.append(cid)

    for cid in sorted(claims):
        visit(cid)
    return ordered


def _evidence_note(
    evidence_id: str,
    evidence: dict[str, dict[str, Any]],
    provenance: dict[str, dict[str, Any]],
) -> str:
    ev = evidence.get(evidence_id)
    if not ev:
        return f"{evidence_id}: canon evidence record missing"
    parts = [_pdf_safe(f"{evidence_id}: {ev.get('label', '')}, 값 {ev.get('value', '')}".strip())]
    prov_ids = [p for p in ev.get("provenance", []) if isinstance(p, str)]
    if prov_ids:
        pdesc = []
        for pid in prov_ids:
            rec = provenance.get(pid, {})
            if rec:
                pdesc.append(
                    f"{pid}({rec.get('artifact_type', '?')}; {rec.get('source_data', '?')}; {rec.get('run_id', '?')})"
                )
            else:
                pdesc.append(f"{pid}(missing)")
        parts.append("출처 " + ", ".join(pdesc))
    checked_by = ev.get("checked_by")
    if checked_by:
        parts.append(f"검증 {checked_by}")
    return "; ".join(parts)


def _pdf_safe(text: str) -> str:
    return text.replace("−", "-")


def render_markdown(project_root: Path) -> str:
    project = project_root / ".project"
    claims = _load_dir(project / "claims", "claim_id")
    evidence = _load_dir(project / "evidence", "evidence_id")
    provenance = _load_dir(project / "provenance", "artifact_id")

    lines = [
        "---",
        "title: \"UMC Canon 기반 국문 논문 초안\"",
        "lang: ko-KR",
        "geometry: margin=25mm",
        "fontsize: 11pt",
        "mainfont: Nanum Gothic",
        "---",
        "",
        "# 초록",
        "",
        "본 문서는 `.project` canon의 claim-evidence-provenance 구조를 결정적으로 직렬화한 국문 학술 논문 골격이다. "
        "본문의 주장 문장과 근거 부착은 canon record에서만 가져오며, 시스템은 새로운 claim 또는 evidence 내용을 생성하지 않는다.",
        "",
        "# 1. 서론",
        "",
        "본 절은 canon에 등록된 주장 구조를 논문 절 구조로 배열한다. 각 주장은 기존 canon의 문장을 사용하고, 근거는 각주로 부착한다.",
        "",
        "# 2. 정당화 그래프",
        "",
    ]

    for index, cid in enumerate(_claim_order(claims), start=1):
        claim = claims[cid]
        sentence = _pdf_safe(str(claim.get("claim") or "").strip())
        ev_ids = [eid for eid in claim.get("evidence", []) if isinstance(eid, str)]
        footnotes = "".join(f"[^{cid}-{eid}]" for eid in ev_ids)
        lines.extend([f"## 2.{index}. {cid}", "", f"{sentence}{footnotes}", ""])
        for eid in ev_ids:
            lines.append(f"[^{cid}-{eid}]: {_evidence_note(eid, evidence, provenance)}")
        if ev_ids:
            lines.append("")

    lines.extend([
        "# 3. 결론",
        "",
        "위 구조는 canon의 현재 claim 위상 순서와 evidence 부착 상태를 반영한다. "
        "추가 산문화는 이 골격의 claim 순서와 evidence 각주를 변경하지 않는 범위에서만 허용된다.",
        "",
    ])
    return "\n".join(lines)


def render_pdf(project_root: Path, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "canon_paper_ko.md"
    pdf_path = output_dir / "canon_paper_ko.pdf"
    markdown_path.write_text(render_markdown(project_root), encoding="utf-8")

    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise RuntimeError("pandoc not found")
    subprocess.run(
        [
            pandoc,
            str(markdown_path),
            "-o",
            str(pdf_path),
            "--pdf-engine=xelatex",
            "-V",
            "mainfont=Nanum Gothic",
        ],
        check=True,
        cwd=str(project_root),
    )
    return markdown_path, pdf_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output-dir", default=".project/outputs")
    args = parser.parse_args()
    root = Path(args.project_root).expanduser().resolve()
    out = Path(args.output_dir).expanduser()
    if not out.is_absolute():
        out = root / out
    md, pdf = render_pdf(root, out)
    print(f"markdown -> {md}")
    print(f"pdf -> {pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
