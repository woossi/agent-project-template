#!/usr/bin/env python3
"""team-umc 거버넌스 대시보드 — 스냅샷 스캐너.

design.md §5·§6 계약을 구현한다. 기존 자산을 읽고, diff 계산을 위해 직전 스냅샷
캐시만 `.context/`에 쓴다(메일박스·스킬 디렉토리·team.json·미리알림 원본은 수정하지 않는다).

스킬/에이전트 '추가 감지'는 직전 스냅샷(.context/dashboard-prev.json)과 diff한다.
미리알림은 비싼 JXA 호출이라 폴링 경로(snapshot)에서는 캐시를 쓰고, 명시 새로고침
(reminders=True)일 때만 reminders_bridge를 호출한다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # 프로젝트 루트 (dashboard/ 의 부모)
TEAMS_DIR = ROOT / "teams"
TEAM_JSON = ROOT / ".project" / "team.json"
PREV_SNAPSHOT = ROOT / ".context" / "dashboard-prev.json"
REMINDERS_CACHE = ROOT / ".context" / "dashboard-reminders-cache.json"
REMINDERS_CLI = ROOT / ".claude" / "skills" / "reminders-team-bridge" / "scripts" / "reminders_bridge.py"

TEAM_COLORS = {
    "data": "var(--team-data)",
    "write": "var(--team-write)",
    "scout": "var(--team-scout)",
    "review": "var(--team-review)",
    "analysis": "var(--team-analysis)",
}
# 거버넌스/조율 발신자로 인정하는 정체성 접미사·이름
LEAD_SUFFIX = "-lead"
ORCH_NAMES = {"orchestrator"}
RECENT_WINDOW_NS = 6 * 60 * 60 * 1_000_000_000  # 최근 6시간을 '최근 추가'로 본다


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_team_json() -> dict:
    d = _load_json(TEAM_JSON) or {}
    return d


def _list_team_skills(team: str) -> list[dict]:
    """팀 스킬 디렉토리를 스캔. 각 스킬의 이름·mtime을 반환(skills.md 등 비-디렉토리 제외)."""
    skills_dir = TEAMS_DIR / team / ".claude" / "skills"
    out = []
    if not skills_dir.is_dir():
        return out
    for child in skills_dir.iterdir():
        # 실제 스킬은 디렉토리(SKILL.md 보유). skills.md 같은 인덱스 파일은 제외.
        if child.is_dir() and not child.name.startswith("."):
            try:
                mtime_ns = child.stat().st_mtime_ns
            except OSError:
                mtime_ns = 0
            out.append({"name": child.name, "mtime_ns": mtime_ns})
    return sorted(out, key=lambda s: s["name"])


def _worker_skill_updates(team: str, members: list[str]) -> list[dict]:
    """각 워커 폴더의 스킬 mtime을 수집(워커 스킬 업데이트 '소식'용).

    워커 스킬은 워커 폴더의 real dir. 공유 스킬은 symlink라 제외(소음 방지) —
    symlink가 아닌 실제 디렉토리만 '워커 전용 스킬'로 본다.
    """
    out = []
    for w in members:
        wdir = TEAMS_DIR / team / w / ".claude" / "skills"
        if not wdir.is_dir():
            continue
        for child in wdir.iterdir():
            if child.is_dir() and not child.is_symlink() and not child.name.startswith("."):
                try:
                    mtime_ns = child.stat().st_mtime_ns
                except OSError:
                    mtime_ns = 0
                out.append({"team": team, "worker": w, "name": child.name, "mtime_ns": mtime_ns})
    return out


def _scan_mailboxes() -> list[dict]:
    """전 팀 메일박스 메시지를 읽어 거버넌스 결정만 추출.

    포함 기준: 발신자가 lead/orchestrator 이거나, verdict/quality_gate 가 있는 메시지.
    (개별 워커의 일상 보고는 제외 — 팀장급 결정·거버넌스만.)
    """
    decisions = []
    if not TEAMS_DIR.is_dir():
        return decisions
    inboxes = [p for p in TEAMS_DIR.glob("*/.claude/inbox") if p.is_dir()]
    orch = TEAMS_DIR / ".orchestrator" / "inbox"
    if orch.is_dir():
        inboxes.append(orch)
    for inbox in inboxes:
        if not inbox.is_dir():
            continue
        msg_paths = list(inbox.glob("*.json"))
        msg_paths.extend((inbox / ".claimed").glob("*.json"))
        msg_paths.extend((inbox / ".consumed").glob("*.json"))
        for msg_path in msg_paths:
            d = _load_json(msg_path)
            if not isinstance(d, dict):
                continue
            sender = str(d.get("from") or "")
            verdict = d.get("verdict")
            qgate = d.get("quality_gate")
            is_lead = sender.endswith(LEAD_SUFFIX) or sender in ORCH_NAMES
            has_gov = verdict not in (None, "None") or qgate not in (None, "None")
            if not (is_lead or has_gov):
                continue
            try:
                ts_ns = int(d.get("ts_ns") or 0)
            except (TypeError, ValueError):
                ts_ns = 0
            decisions.append({
                "id": d.get("id"),
                "from": sender,
                "team": d.get("sender_team") or d.get("to_team"),
                "to_team": d.get("to_team"),
                "state": "claimed" if msg_path.parent.name == ".claimed" else (
                    "consumed" if msg_path.parent.name == ".consumed" else "unclaimed"
                ),
                "subject": d.get("subject") or "",
                "body": d.get("body") or "",
                "ts_ns": ts_ns,
                "verdict": None if verdict in (None, "None") else verdict,
                "quality_gate": None if qgate in (None, "None") else qgate,
                "work_ref": None if d.get("work_ref") in (None, "None") else d.get("work_ref"),
                "reply_to": None if d.get("reply_to") in (None, "None") else d.get("reply_to"),
                "claimed_by": None if d.get("claimed_by") in (None, "None") else d.get("claimed_by"),
            })
    decisions.sort(key=lambda x: x["ts_ns"], reverse=True)
    return decisions


def _promotion_signals() -> list[dict]:
    """detect_team_promotions.py 가 띄운 후보를 소식으로(있으면). best-effort."""
    hook = ROOT / ".claude" / "hooks" / "detect_team_promotions.py"
    if not hook.exists():
        return []
    try:
        res = subprocess.run(
            [sys.executable, str(hook)],
            capture_output=True, text=True, timeout=10, cwd=str(ROOT),
        )
        out = (res.stdout or "") + (res.stderr or "")
        signals = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("- [") and "team" in line:
                signals.append({"kind": "promotion_signal", "team": None, "detail": line[:200], "ts_ns": 0})
        return signals[:8]
    except Exception:
        return []


def _reminders_cached() -> list[dict]:
    """캐시된 미리알림 스냅샷만 반환(JXA 호출 없음 — 폴링 경로 전용, 절대 안 막힘)."""
    cached = _load_json(REMINDERS_CACHE)
    if isinstance(cached, dict) and isinstance(cached.get("reminders"), list):
        return cached["reminders"]
    return []


def refresh_reminders(timeout_s: int = 45) -> list[dict]:
    """미리알림을 JXA로 실제 갱신하고 캐시에 쓴다. 느림(osascript). 명시 새로고침에서만 호출.

    실패(타임아웃·권한)해도 예외를 던지지 않고 기존 캐시 또는 빈 배열로 우아하게 빠진다.
    """
    if not REMINDERS_CLI.exists():
        return _reminders_cached()
    try:
        res = subprocess.run(
            [sys.executable, str(REMINDERS_CLI), "list-teams"],
            capture_output=True, text=True, timeout=timeout_s, cwd=str(ROOT),
        )
        data = json.loads(res.stdout or "{}")
        items = data.get("result", data)
        if isinstance(items, dict):
            items = items.get("teams", [])
        out = []
        for it in items or []:
            name = str(it.get("team", ""))
            if name.lower().startswith("umc"):
                out.append({"list": name, "open": it.get("open", 0), "total": it.get("total", 0)})
        out.sort(key=lambda r: (r["list"] != "umc", r["list"]))  # umc 먼저
        REMINDERS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        REMINDERS_CACHE.write_text(
            json.dumps({"reminders": out, "refreshed_ts_ns": time.time_ns()}, ensure_ascii=False),
            encoding="utf-8",
        )
        return out
    except Exception:
        return _reminders_cached()


def build_snapshot(reminders_force: bool = False) -> dict:
    now_ns = time.time_ns()
    team_json = _read_team_json()
    subteams = team_json.get("subteams", []) or []

    prev = _load_json(PREV_SNAPSHOT) or {}
    prev_teams = {t.get("name"): t for t in prev.get("teams", [])} if isinstance(prev, dict) else {}

    decisions = _scan_mailboxes()
    teams_out = []
    news = []

    # 미리알림을 먼저 수집해 list 이름으로 인덱싱(각 팀 카드에 자기 팀 목록을 넣기 위해).
    reminders = refresh_reminders() if reminders_force else _reminders_cached()
    rem_by_list = {r.get("list"): r for r in reminders}

    for st in subteams:
        name = st.get("name")
        members = st.get("members", []) or []
        lead = st.get("orchestrator")
        # 이 팀의 미리알림 목록(team.json의 reminders_list, 기본 umc-<팀명>).
        team_rem_list = st.get("reminders_list") or f"umc-{name}"
        team_reminder = rem_by_list.get(team_rem_list)
        team_skills = _list_team_skills(name)
        skill_names = [s["name"] for s in team_skills]

        # 직전 스냅샷 대비 추가 감지. 직전에 이 팀이 '존재했는지'(키 유무)로 판단해야
        # 빈 리스트(스킬 0개였음)와 '스냅샷 없음'을 구분한다 — 첫 실행 시 전체를
        # 신규로 오인하지 않으면서, 0→1 추가는 정확히 잡는다.
        had_prev_team = name in prev_teams
        prev_t = prev_teams.get(name, {})
        prev_skills = set(prev_t.get("team_skills", []) or [])
        prev_members = set(prev_t.get("members", []) or [])
        added_skills = [s for s in skill_names if s not in prev_skills] if had_prev_team else []
        added_agents = [m for m in members if m not in prev_members] if had_prev_team else []

        # 최근 추가(mtime 기준) — 직전 스냅샷이 없을 때의 1차 추정
        recent_skill = sum(1 for s in team_skills if now_ns - s["mtime_ns"] < RECENT_WINDOW_NS)

        # 팀의 최근 결정(발신자=팀장)
        team_decisions = [d for d in decisions if d.get("team") == name or (d.get("from") or "").startswith(name)]
        latest = team_decisions[0] if team_decisions else None
        # verdict 집계
        verdict = None
        for d in team_decisions:
            if d.get("verdict"):
                v = d["verdict"]
                result = v.get("result") if isinstance(v, dict) else str(v)
                verdict = {"result": result, "count": 1}
                break

        teams_out.append({
            "name": name,
            "color": TEAM_COLORS.get(name, "var(--text-secondary)"),
            "lead": lead,
            "members": members,
            "team_skills": skill_names,
            # 직전 스냅샷이 있으면 diff(added_skills)가 정본, 없을 때만 mtime 추정으로 폴백.
            # (배지가 6h 동안 과다 카운트하던 버그 수정: recent_skill을 첫 실행에만 쓴다.)
            "team_skill_added_recent": len(added_skills) if had_prev_team else recent_skill,
            "agent_added_recent": len(added_agents),
            "latest_decision": ({"id": latest["id"], "subject": latest["subject"], "ts_ns": latest["ts_ns"]}
                                if latest else None),
            "verdict": verdict,
            # 사용자 요청: 각 팀 카드에 자기 팀 미리알림 목록을 넣는다.
            "reminder": ({"list": team_rem_list, "open": team_reminder.get("open", 0),
                          "total": team_reminder.get("total", 0)} if team_reminder
                         else {"list": team_rem_list, "open": None, "total": None}),
        })

        # 소식: 팀 스킬 추가
        for s in added_skills:
            news.append({"kind": "team_skill_added", "team": name, "name": s, "ts_ns": now_ns})
        # 소식: 에이전트(워커) 추가
        for m in added_agents:
            news.append({"kind": "agent_added", "team": name, "name": m, "ts_ns": now_ns})
        # 소식: 워커 스킬 업데이트 (mtime 변화 — 직전 스냅샷의 mtime과 비교)
        prev_wskills = {(w.get("team"), w.get("worker"), w.get("name")): w.get("mtime_ns", 0)
                        for w in prev_t.get("_worker_skills", [])} if prev_t else {}
        cur_wskills = _worker_skill_updates(name, members)
        for w in cur_wskills:
            key = (w["team"], w["worker"], w["name"])
            prev_mt = prev_wskills.get(key)
            if prev_mt is None:
                # 새 워커 스킬. 첫 실행(직전 스냅샷 없음)에는 team/agent 소식과 일관되게
                # 억제한다 — 그래야 신규 배포 시 기존 스킬 전부가 유령 '신규'로 뜨지 않는다.
                if had_prev_team:
                    news.append({"kind": "worker_skill_updated", "team": name,
                                 "worker": w["worker"], "name": w["name"], "ts_ns": w["mtime_ns"],
                                 "new": True})
            elif w["mtime_ns"] > prev_mt:
                news.append({"kind": "worker_skill_updated", "team": name,
                             "worker": w["worker"], "name": w["name"], "ts_ns": w["mtime_ns"]})
        # 워커 스킬 mtime을 다음 비교용으로 팀 객체에 박제
        teams_out[-1]["_worker_skills"] = cur_wskills

    # 승격 신호 소식
    news.extend(_promotion_signals())
    news.sort(key=lambda n: n.get("ts_ns", 0), reverse=True)

    snapshot = {
        "generated_ts_ns": now_ns,
        "teams": teams_out,
        "decisions": decisions[:60],
        "news": news[:40],
        "reminders": refresh_reminders() if reminders_force else _reminders_cached(),
    }

    # 다음 diff를 위해 현재 스냅샷 저장(소식은 빼고 비교 기준만)
    try:
        PREV_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        PREV_SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass

    # 응답에서는 내부용 _worker_skills 제거(계약 외 필드)
    for t in snapshot["teams"]:
        t.pop("_worker_skills", None)
    return snapshot


if __name__ == "__main__":
    force = "--reminders" in sys.argv
    print(json.dumps(build_snapshot(reminders_force=force), ensure_ascii=False, indent=2))
