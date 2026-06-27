#!/usr/bin/env python3
"""대시보드 내장 자동화 스케줄러.

Claude 세션 cron은 'REPL이 idle일 때·세션이 살아있을 때만' 발화하는 한계가 있다
(세션이 바쁘면 밀리고, 닫히면 멈춘다). 이 모듈은 대시보드 서버 프로세스 안에서
도는 OS 타이머 기반 스케줄러라, 세션·idle과 무관하게 interval마다 발화한다.

발화 = 각 target peer를 헤드리스 `claude`로 깨워 자기 채널을 점검·진행하게 한다.
설정(enabled·interval·targets)은 automation.json 단일 출처에서 읽고 쓴다. UI에서
켜고/끄고/주기를 조정하면 이 파일이 갱신되고 스케줄러가 다음 tick에 반영한다.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG = HERE / "automation.json"
LOG = ROOT / ".context" / "dashboard-automation.log.jsonl"

# 깨울 수 있는 정체성(로스터 + orchestrator). team.json에서 동적 로드.
TEAM_JSON = ROOT / ".project" / "team.json"
_RUNNING: dict[str, subprocess.Popen] = {}

DEFAULT_CONFIG = {
    "enabled": False,           # 기본 꺼짐 — 사용자가 UI에서 명시적으로 켠다.
    "interval_min": 10,         # 사용자 결정: 10분.
    "targets": ["orchestrator"],  # 기본은 orchestrator만. UI에서 워커·팀장 추가.
    "last_tick_ts_ns": None,
    "next_tick_ts_ns": None,
    "dry_run": True,            # 기본 dry_run: 실제 claude 실행 대신 '깨울 것'만 기록.
}


def _roster() -> list[str]:
    try:
        d = json.loads(TEAM_JSON.read_text(encoding="utf-8"))
        members = list(d.get("members", []))
        return ["orchestrator"] + members  # orchestrator는 비-멤버 가상 정체성
    except Exception:
        return ["orchestrator"]


def _team_json() -> dict:
    try:
        data = json.loads(TEAM_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _identity_cwd(identity: str) -> Path:
    if identity == "orchestrator":
        return ROOT
    for st in _team_json().get("subteams") or []:
        if not isinstance(st, dict):
            continue
        team = st.get("name")
        members = st.get("members") or []
        if isinstance(team, str) and identity in members:
            candidate = ROOT / "teams" / team / identity
            return candidate if candidate.is_dir() else ROOT
    return ROOT


def load_config() -> dict:
    if CONFIG.exists():
        try:
            cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
            # 기본값 채우기(누락 키 방어)
            merged = dict(DEFAULT_CONFIG)
            merged.update(cfg)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> dict:
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg or {})
    # interval은 1~120분으로 클램프
    try:
        merged["interval_min"] = max(1, min(120, int(merged.get("interval_min", 10))))
    except (TypeError, ValueError):
        merged["interval_min"] = 10
    # targets는 로스터 안의 것만 허용
    valid = set(_roster())
    merged["targets"] = [t for t in (merged.get("targets") or []) if t in valid] or ["orchestrator"]
    merged["enabled"] = bool(merged.get("enabled"))
    merged["dry_run"] = bool(merged.get("dry_run", True))
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.parent / (CONFIG.name + ".tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG)
    return merged


def _log_event(rec: dict) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def recent_log(n: int = 20) -> list[dict]:
    if not LOG.exists():
        return []
    try:
        lines = LOG.read_text(encoding="utf-8").splitlines()[-n:]
        return [json.loads(x) for x in lines if x.strip()]
    except Exception:
        return []


def _wake_peer(identity: str, dry_run: bool, now_ns: int) -> dict:
    """한 peer를 헤드리스 claude로 깨운다. dry_run이면 실행 대신 기록만."""
    prompt = (f"[자동 10분 점검/{identity}] 자기 채널을 점검·진행하라. "
              f"규약: .project/memory/agent-respawn-interval.json. "
              f"변동 없으면 '변동 없음'만 남기고 종료.")
    if dry_run:
        rec = {"ts_ns": now_ns, "identity": identity, "mode": "dry_run", "ok": True,
               "note": "dry_run — 실제 claude 미실행(깨울 대상만 기록)"}
        _log_event(rec)
        return rec
    running = _RUNNING.get(identity)
    if running is not None:
        rc = running.poll()
        if rc is None:
            rec = {"ts_ns": now_ns, "identity": identity, "mode": "skip_running", "ok": True,
                   "pid": running.pid, "note": "이미 실행 중 — 중복 기동 생략"}
            _log_event(rec)
            return rec
        _RUNNING.pop(identity, None)
        _log_event({"ts_ns": now_ns, "identity": identity, "mode": "reaped", "ok": rc == 0,
                    "pid": running.pid, "returncode": rc})
    try:
        env = dict(os.environ, CLAUDE_AGENT_NAME=identity, CLAUDE_PROJECT_DIR=str(ROOT))
        # 헤드리스 비대화 실행. -p(프린트 모드)로 한 번 돌고 종료.
        proc = subprocess.Popen(
            ["claude", "-p", prompt],
            cwd=str(_identity_cwd(identity)), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _RUNNING[identity] = proc
        rec = {"ts_ns": now_ns, "identity": identity, "mode": "spawn", "ok": True,
               "pid": proc.pid, "note": "headless claude 기동"}
    except Exception as e:
        rec = {"ts_ns": now_ns, "identity": identity, "mode": "spawn", "ok": False,
               "note": f"기동 실패: {e}"}
    _log_event(rec)
    return rec


class Scheduler:
    """대시보드 서버 프로세스 안에서 도는 자동화 스케줄러(데몬 스레드)."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        # 30초마다 깨어나 enabled·interval을 확인하고, 주기가 지났으면 발화.
        while not self._stop.is_set():
            cfg = load_config()
            now_ns = time.time_ns()
            if cfg.get("enabled"):
                interval_ns = int(cfg.get("interval_min", 10)) * 60 * 1_000_000_000
                last = cfg.get("last_tick_ts_ns")
                due = last is None or (now_ns - int(last)) >= interval_ns
                if due:
                    for ident in cfg.get("targets", ["orchestrator"]):
                        _wake_peer(ident, cfg.get("dry_run", True), now_ns)
                    cfg["last_tick_ts_ns"] = now_ns
                    cfg["next_tick_ts_ns"] = now_ns + interval_ns
                    save_config(cfg)
                else:
                    # 다음 발화 예정 갱신(표시용)
                    if last is not None:
                        cfg["next_tick_ts_ns"] = int(last) + interval_ns
                        save_config(cfg)
            self._stop.wait(30)  # 30초 폴
