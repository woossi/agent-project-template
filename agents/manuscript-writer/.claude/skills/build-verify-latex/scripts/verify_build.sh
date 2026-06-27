#!/usr/bin/env bash
# build-verify-latex: 원고 LaTeX 빌드 수렴 검증 (결정적·멱등적)
#
# latexmk 단일 호출의 패스 부족 함정(undefined citation/reference 잔존)을 회피하기 위해
# 명시적 다중 패스(xelatex → bibtex → xelatex×3)로 강제 수렴시키고 게이트를 판정한다.
#
# 사용법: verify_build.sh <master.tex>
#   예) verify_build.sh /Users/ujunbin/research/UMC/umc_paper.tex
#
# 종료코드: 0 = 모든 게이트 통과(PASS), 1 = 하나 이상 실패(FAIL) 또는 인자 오류.
# stdout: 사람이 읽는 게이트 표 + 마지막 줄에 RESULT=PASS|FAIL.
set -euo pipefail

MASTER="${1:-}"
if [[ -z "$MASTER" || ! -f "$MASTER" ]]; then
  echo "ERROR: master .tex 인자가 없거나 파일이 없음: '${MASTER}'" >&2
  echo "사용법: verify_build.sh <master.tex>" >&2
  exit 1
fi

DIR="$(cd "$(dirname "$MASTER")" && pwd)"
BASE="$(basename "$MASTER" .tex)"
cd "$DIR"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: 필수 도구 없음: $1" >&2; exit 1; }; }
need xelatex
need bibtex

# ---------- 0. 변경 파일 환경 균형 사전점검 (마스터 + \input 파트) ----------
inputs=$(grep -oE '\\(input|include)\{[^}]+\}' "$BASE.tex" 2>/dev/null \
  | sed -E 's/\\(input|include)\{([^}]+)\}/\2/' | sed -E 's/$/.tex/; s/\.tex\.tex$/.tex/' || true)
balance_fail=0
check_balance() {
  local f="$1"; [[ -f "$f" ]] || return 0
  # grep 비매치는 exit 1 → set -e 발동 방지 위해 모두 '|| true'로 흡수
  local d fb fe ab ae
  d=$( { grep -o '\$' "$f" || true; } | wc -l | tr -d ' ')
  fb=$(grep -c 'begin{figure' "$f" || true); fe=$(grep -c 'end{figure' "$f" || true)
  ab=$(grep -c 'begin{align'  "$f" || true); ae=$(grep -c 'end{align'  "$f" || true)
  if (( d % 2 != 0 )) || (( fb != fe )) || (( ab != ae )); then
    echo "  [BALANCE-FAIL] $f : \$=$d figure=$fb/$fe align=$ab/$ae"
    balance_fail=1
  fi
}
echo "== 1) 환경 균형 사전점검 =="
check_balance "$BASE.tex"
for p in $inputs; do check_balance "$p"; done
(( balance_fail == 0 )) && echo "  [OK] \$ 짝수 / figure·align begin=end"

# ---------- 1. 명시적 다중 패스 (패스부족 함정 회피의 핵심) ----------
echo "== 2) 빌드 패스 (xelatex → bibtex → xelatex×3) =="
latexmk -C "$BASE.tex" >/dev/null 2>&1 || true   # 캐시 제거(없어도 무해)
xelatex -interaction=nonstopmode -halt-on-error "$BASE.tex" >"$TMP/p0.log" 2>&1 || true
bibtex "$BASE" >"$TMP/bib.log" 2>&1 || true
for i in 1 2 3; do
  xelatex -interaction=nonstopmode -halt-on-error "$BASE.tex" >"$TMP/p$i.log" 2>&1 || true
done
FINAL="$TMP/p3.log"

# ---------- 2. 게이트 판정 (최종 패스 로그 + bibtex 로그) ----------
# grep -c 비매치(exit 1)를 '|| true'로, 빈 값은 0으로 보정(산술비교 안전)
num() { local v="${1:-0}"; [[ "$v" =~ ^[0-9]+$ ]] && echo "$v" || echo 0; }
g_cite=$(num "$(grep -ci 'undefined citation' "$FINAL" || true)")
g_ref=$(num "$(grep -ciE 'Warning:.*(Reference|Citation).*undefined' "$FINAL" || true)")
g_rerun=$(num "$(grep -ci 'rerun to' "$FINAL" || true)")
g_err=$(num "$(grep -ciE '^!|Fatal error|Emergency stop' "$FINAL" || true)")
g_bibwarn=$(num "$(grep -ci 'error' "$TMP/bib.log" || true)")

# PDF 본문 미해소 마커(??) — pdftotext 있을 때만
g_marker="skip"
if command -v pdftotext >/dev/null 2>&1 && [[ -f "$BASE.pdf" ]]; then
  pdftotext "$BASE.pdf" "$TMP/body.txt" 2>/dev/null || true
  g_marker=$(num "$(grep -c '??' "$TMP/body.txt" || true)")
fi

pages="?"
if command -v pdfinfo >/dev/null 2>&1 && [[ -f "$BASE.pdf" ]]; then
  pages=$(pdfinfo "$BASE.pdf" 2>/dev/null | awk '/^Pages:/{print $2}')
fi

echo "== 3) 게이트 =="
printf "  undefined citation : %s\n" "$g_cite"
printf "  undefined reference: %s\n" "$g_ref"
printf "  rerun 권고         : %s\n" "$g_rerun"
printf "  Error/Fatal        : %s\n" "$g_err"
printf "  bibtex error       : %s\n" "$g_bibwarn"
printf "  PDF 미해소 마커(??) : %s\n" "$g_marker"
printf "  PDF 페이지          : %s\n" "$pages"

fail=0
(( balance_fail != 0 )) && fail=1
(( g_cite  != 0 )) && fail=1
(( g_ref   != 0 )) && fail=1
(( g_rerun != 0 )) && fail=1
(( g_err   != 0 )) && fail=1
(( g_bibwarn != 0 )) && fail=1
[[ "$g_marker" != "skip" ]] && (( g_marker != 0 )) && fail=1
[[ ! -f "$BASE.pdf" ]] && fail=1

if (( fail == 0 )); then
  echo "RESULT=PASS"
  exit 0
else
  echo "RESULT=FAIL"
  echo "  (실패 게이트의 로그는 빌드 디렉토리에서 재현: 위 패스 순서대로 직접 실행해 원인 확인)"
  exit 1
fi
