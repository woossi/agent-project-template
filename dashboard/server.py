#!/usr/bin/env python3
"""team-umc 거버넌스 대시보드 — 로컬 웹 서버 (Python stdlib only).

design.md §5 아키텍처: stateless, 127.0.0.1 바인드, 별도 프로세스라 TUI와 0 결합.

라우트:
  GET  /                      -> index.html
  GET  /style.css, /app.js    -> 정적
  GET  /api/snapshot          -> scan.build_snapshot() (폴링 경로, 캐시 미리알림, 빠름)
  GET  /api/snapshot?reminders=1 -> 미리알림 JXA 강제 갱신 포함(느림, 명시 새로고침)
  POST /api/checkback         -> 미리알림 체크백 쓰기(annotate/complete), 확인은 클라가 함

실행: python3 dashboard/server.py [--port 8787]
"""
from __future__ import annotations

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import scan  # noqa: E402
import automation  # noqa: E402

REMINDERS_CLI = ROOT / ".claude" / "skills" / "reminders-team-bridge" / "scripts" / "reminders_bridge.py"

STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    # 로그 소음 억제(터미널 깔끔)
    def log_message(self, *args):
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, fname, ctype):
        path = HERE / fname
        if not path.exists():
            self.send_error(404, "not found")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # XSS 심층 방어: 인라인 이벤트 핸들러·외부 스크립트 실행 차단(self만 허용).
        if fname == "index.html":
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        if route in STATIC:
            self._send_static(*STATIC[route])
            return
        if route == "/api/snapshot":
            qs = parse_qs(parsed.query)
            force = qs.get("reminders", ["0"])[0] in ("1", "true", "yes")
            try:
                snap = scan.build_snapshot(reminders_force=force)
                self._send_json(snap)
            except Exception:
                self._send_json({"error": "스냅샷 생성 오류"}, status=500)
            return
        if route == "/api/reminder-tasks":
            # 한 목록의 open 작업 제목들(체크백 드롭다운·§4.2 드릴다운용). 읽기 전용.
            qs = parse_qs(parsed.query)
            list_name = (qs.get("list", [""])[0] or "").strip()
            if not list_name:
                self._send_json({"ok": False, "error": "list 필요"}, status=400)
                return
            try:
                r = subprocess.run(
                    [sys.executable, str(REMINDERS_CLI), "pull", list_name],
                    capture_output=True, text=True, timeout=45, cwd=str(ROOT),
                )
                data = json.loads(r.stdout or "{}")
                tasks = data.get("result", []) if isinstance(data, dict) else []
                out = [{"id": t.get("id"), "name": t.get("name"),
                        "completed": t.get("completed", False)}
                       for t in tasks if isinstance(t, dict)]
                self._send_json({"ok": True, "list": list_name, "tasks": out})
            except Exception:
                self._send_json({"ok": False, "error": "작업 목록 조회 오류"}, status=500)
            return
        if route == "/api/automation":
            cfg = automation.load_config()
            self._send_json({"ok": True, "config": cfg,
                             "roster": automation._roster(),
                             "log": automation.recent_log(15)})
            return
        self.send_error(404, "not found")

    def _csrf_ok(self) -> bool:
        """로컬 CSRF 방어: Origin/Referer가 자기 출처가 아니면 거부.

        쓰기 엔드포인트라 같은 머신의 악성 웹페이지가 fetch로 미리알림을 변조하는
        걸 막는다. Origin이 있으면 그것을, 없으면 Referer를, 둘 다 없으면(동일 출처
        fetch는 보통 Origin을 보냄) 보수적으로 허용하지 않는다."""
        host = self.headers.get("Host", "")
        allowed = {f"http://{host}", f"http://127.0.0.1", f"http://localhost"}
        origin = self.headers.get("Origin")
        if origin is not None:
            return any(origin == a or origin.startswith(a + ":") for a in allowed) or origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:")
        referer = self.headers.get("Referer", "")
        return referer.startswith("http://127.0.0.1") or referer.startswith("http://localhost") or referer.startswith(f"http://{host}")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/checkback", "/api/automation"):
            self.send_error(404, "not found")
            return
        if not self._csrf_ok():
            self._send_json({"ok": False, "error": "cross-origin 요청 거부"}, status=403)
            return
        # 쓰기는 JSON Content-Type을 강제 → simple-request CSRF 우회 차단.
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if ctype != "application/json":
            self._send_json({"ok": False, "error": "application/json 필요"}, status=415)
            return
        # 자동화 설정 변경(UI에서 ON/OFF·주기·타깃 조정)
        if parsed.path == "/api/automation":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b"{}"
                req = json.loads(raw or b"{}")
            except Exception as e:
                self._send_json({"ok": False, "error": f"bad request: {e}"}, status=400)
                return
            cur = automation.load_config()
            # 변경 가능한 필드만 병합(last_tick 등 내부 상태는 보존)
            for k in ("enabled", "interval_min", "targets", "dry_run"):
                if k in req:
                    cur[k] = req[k]
            saved = automation.save_config(cur)
            self._send_json({"ok": True, "config": saved})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            req = json.loads(raw or b"{}")
        except Exception as e:
            self._send_json({"ok": False, "error": f"bad request: {e}"}, status=400)
            return

        list_name = (req.get("list") or "").strip()
        task_id = (req.get("task_id") or "").strip()
        task_name = (req.get("task_name") or req.get("task_id_or_name") or "").strip()
        note = req.get("note") or ""
        do_complete = bool(req.get("complete"))

        if not list_name or (not task_id and not task_name):
            self._send_json({"ok": False, "error": "list와 작업(task_id 또는 task_name) 필수"}, status=400)
            return
        # no-op(노트도 완료도 없음)을 실패로 혼동하지 않도록 명시 거부.
        if not note and not do_complete:
            self._send_json({"ok": False, "error": "note 또는 complete 중 하나는 필요합니다."}, status=400)
            return

        # 작업 선택자: id가 있으면 --id(안정적·정확), 없으면 --name(제목 정확일치).
        sel = ["--id", task_id] if task_id else ["--name", task_name]

        # 미리알림 체크백: annotate(노트 append) 후 선택적으로 complete.
        # reminders_bridge CLI 시그니처: `annotate <team> <note> [--id|--name <sel>]`,
        # `complete <team> [--id|--name <sel>]` — team·note는 위치 인자다(플래그 아님).
        results = []
        try:
            if note:
                cmd = [sys.executable, str(REMINDERS_CLI), "annotate",
                       list_name, note] + sel
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=45, cwd=str(ROOT))
                results.append({"op": "annotate", "rc": r.returncode,
                                "out": (r.stdout or r.stderr)[:300]})
            if do_complete:
                cmd = [sys.executable, str(REMINDERS_CLI), "complete", list_name] + sel
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=45, cwd=str(ROOT))
                results.append({"op": "complete", "rc": r.returncode,
                                "out": (r.stdout or r.stderr)[:300]})
            ok = all(x["rc"] == 0 for x in results) if results else False
            # 체크백 후 미리알림 캐시 갱신(백로그 카운트 반영)
            if ok:
                scan.refresh_reminders(timeout_s=45)
            self._send_json({"ok": ok, "results": results})
        except Exception:
            # 내부 절대경로·스택이 클라로 새지 않도록 일반 메시지만 반환.
            self._send_json({"ok": False, "error": "체크백 실행 중 오류", "results": results}, status=500)


def main():
    port = 8787
    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except (IndexError, ValueError):
            pass
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    # 자동화 스케줄러 기동(서버 프로세스 안 OS 타이머 — 세션·idle 무관하게 발화).
    sched = automation.Scheduler()
    sched.start()
    cfg = automation.load_config()
    print(f"team-umc 거버넌스 대시보드 → http://127.0.0.1:{port}")
    print(f"자동화: {'ON' if cfg.get('enabled') else 'OFF'} · {cfg.get('interval_min')}분 주기"
          f" · {'dry-run' if cfg.get('dry_run') else '실제 실행'} (UI에서 조정)")
    print("종료: Ctrl+C")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료됨")
        sched.stop()
        httpd.shutdown()


if __name__ == "__main__":
    main()
