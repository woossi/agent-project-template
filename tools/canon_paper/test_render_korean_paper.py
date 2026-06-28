#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import render_korean_paper as rkp


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class RenderKoreanPaperTest(unittest.TestCase):
    def test_markdown_preserves_claim_text_and_attaches_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".project/claims/C001__a.json",
                {"claim_id": "C001", "claim": "사용자 입력 주장이다.", "evidence": ["E001"], "relations": []},
            )
            _write(
                root / ".project/evidence/E001__a.json",
                {"evidence_id": "E001", "label": "근거명", "value": "값", "provenance": ["P001"], "status": "active"},
            )
            _write(
                root / ".project/provenance/P001__a.json",
                {"artifact_id": "P001", "artifact_type": "model_result", "source_data": "D001", "run_id": "RUN001"},
            )
            md = rkp.render_markdown(root)
            self.assertIn("사용자 입력 주장이다.[^C001-E001]", md)
            self.assertIn("[^C001-E001]: E001: 근거명, 값 값; 출처 P001", md)

    def test_claim_order_respects_depends_on(self) -> None:
        claims = {
            "C002": {"relations": [{"type": "depends_on", "target": "C001"}]},
            "C001": {"relations": []},
        }
        self.assertEqual(rkp._claim_order(claims), ["C001", "C002"])


if __name__ == "__main__":
    unittest.main()
