"""dashboard scan tests."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan  # noqa: E402


def test_promotion_signals_use_evaluate_mode_and_candidate_shard(monkeypatch, tmp_path):
    hook = tmp_path / ".claude" / "hooks" / "detect_team_promotions.py"
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/usr/bin/env python3\n")
    shard = tmp_path / ".project" / "promotions" / "candidates" / "team.json"
    shard.parent.mkdir(parents=True)
    shard.write_text(json.dumps({
        "team_skill": [{
            "kind": "team_skill",
            "key": "write",
            "team": "write",
            "intra_handoffs": 31,
            "distinct_agents": 3,
        }],
        "project_skill": [{
            "kind": "project_skill",
            "key": "review+write",
            "inter_handoffs": 85,
            "directions": 2,
        }],
    }))

    calls = []

    def fake_run(argv, **kwargs):
        calls.append({"argv": [str(a) for a in argv], **kwargs})
        return SimpleNamespace(returncode=0, stdout=f"2 candidates -> {shard}\n", stderr="")

    monkeypatch.setattr(scan, "ROOT", tmp_path)
    monkeypatch.setattr(scan.subprocess, "run", fake_run)

    signals = scan._promotion_signals()

    assert calls
    assert calls[0]["argv"][2:4] == ["evaluate", "--project-root"]
    assert calls[0]["argv"][4] == str(tmp_path)
    assert calls[0]["stdin"] is subprocess.DEVNULL
    assert len(signals) == 2
    assert signals[0]["kind"] == "promotion_signal"
    assert "team_skill" in signals[0]["detail"]
    assert "write" in signals[0]["detail"]
    assert "project_skill" in signals[1]["detail"]
    assert "review+write" in signals[1]["detail"]


def test_build_snapshot_force_refreshes_reminders_once(monkeypatch, tmp_path):
    calls = []

    def fake_refresh(timeout_s=45):
        calls.append(timeout_s)
        return [{"list": "umc", "open": 1, "total": 2}]

    monkeypatch.setattr(scan, "PREV_SNAPSHOT", tmp_path / "prev.json")
    monkeypatch.setattr(scan, "_read_team_json", lambda: {"subteams": []})
    monkeypatch.setattr(scan, "_scan_mailboxes", lambda: [])
    monkeypatch.setattr(scan, "_promotion_signals", lambda: [])
    monkeypatch.setattr(scan, "refresh_reminders", fake_refresh)

    snap = scan.build_snapshot(reminders_force=True)

    assert calls == [45]
    assert snap["reminders"] == [{"list": "umc", "open": 1, "total": 2}]
