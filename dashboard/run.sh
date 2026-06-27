#!/usr/bin/env bash
# team-umc 거버넌스 대시보드 실행. TUI와 분리된 별도 프로세스로 뜬다(렉 0).
# 사용: bash dashboard/run.sh [포트]   (기본 8787)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${1:-8787}"
echo "team-umc 거버넌스 관제탑 기동 → http://127.0.0.1:${PORT}"
echo "브라우저에서 위 주소를 여세요. 종료는 Ctrl+C."
exec python3 "${HERE}/server.py" --port "${PORT}"
