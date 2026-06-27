# team-umc 거버넌스 대시보드

14 peer 에이전트의 개별 워커 버퍼를 보지 않고도, **팀장급 결정·거버넌스 이벤트**만 한눈에 보는 로컬 웹 대시보드. 터미널 TUI와 **완전히 분리된 별도 프로세스**라 TUI 멈춤·렉을 일으키지 않는다.

설계 전문: [`design.md`](./design.md) (Apple HIG × Claude 디자인).

## 실행

```bash
bash dashboard/run.sh           # 기본 포트 8787
bash dashboard/run.sh 9000      # 포트 지정
```

브라우저에서 `http://127.0.0.1:8787` 을 연다. 종료는 `Ctrl+C`.

## 무엇을 보여주나

| 영역 | 내용 | 사용자 요구 대응 |
| --- | --- | --- |
| **미리알림 백로그** | `umc`·`umc-data`… 목록의 open/total | 미리알림 연동 재건(읽기) |
| **팀 단위 자원** (5 카드) | 팀장·워커·**＋스킬 추가**·**＋에이전트 추가**·최근 결정·verdict | 팀장의 팀 단위 자원·에이전트·스킬 추가 여부 |
| **팀장 결정 피드** | lead/orchestrator 발신 메시지·verdict 타임라인 | 팀장급 결정 결과·어떤 스킬이 관리되는지 |
| **스킬·에이전트 소식** | 팀스킬 추가·에이전트 추가·**워커 스킬 업데이트**·승격 신호 | 개별 워커의 스킬 업데이트 소식화 |
| **결정 디테일 + 체크백** | 결정 본문 + **미리알림에 진행상태 기록** | 미리알림 연동 재건(쓰기) |

개별 워커 버퍼는 **표시하지 않는다**(렉·소음의 원인 — design.md §8 비범위).

## 자동화 (주기 재기동) — UI에서 제어

10분 재기동을 **대시보드 UI에서 켜고/끄고/주기를 조정**한다. 상단 "자동화" 패널:

- **토글**: ON/OFF. 마지막/다음 발화 시각이 표시되어 실제 도는지 투명하게 보인다.
- **주기**: 1~120분.
- **타깃**: 깨울 정체성 선택(orchestrator·팀장·워커). 기본 orchestrator만.
- **dry-run**: 기본 켜짐 — 실제 `claude`를 실행하지 않고 "깨울 대상"만 로그에 남긴다(안전·토큰 0). 끄면 헤드리스 `claude -p`로 각 타깃을 실제 기동한다(확인 다이얼로그 거침).
- **최근 발화 로그**: 각 tick에 무엇을 깨웠는지.

**왜 서버 스케줄러인가** — Claude 세션 `cron`은 "REPL이 idle일 때·세션이 살아있을 때만" 발화해, 세션이 바쁘거나 닫히면 멈춘다(실제로 안 돌던 원인). 대신 **대시보드 서버 프로세스 안의 OS 타이머**(`automation.py`의 Scheduler 데몬 스레드)가 30초마다 깨어나 주기를 확인하고 발화하므로, 세션·idle과 무관하게 서버가 떠 있는 한 동작한다. 설정 단일 출처는 `dashboard/automation.json`, 발화 로그는 `.context/dashboard-automation.log.jsonl`.

## 왜 렉이 없나 (design.md §5)

1. 별도 OS 프로세스(Python http + 브라우저). 터미널 렌더 루프와 0 결합.
2. 백엔드 stateless: 매 요청마다 디스크 스냅샷만 read(상주 워처 없음). 폴링 경로 ~35ms.
3. 미리알림 JXA(느림)는 폴링에서 제외 — 캐시를 쓰고, `↻ 미리알림` 버튼·첫 로드에서만 실제 갱신.
4. 클라이언트 diff 패치: 새 이벤트만 DOM 입장(전체 리렌더 금지 → 점프·페인트 폭주 없음).

## 구성

```
dashboard/
  design.md     설계 (Apple × Claude, 전 컴포넌트 명세)
  scan.py       read-only 스냅샷 스캐너 (메일박스·스킬·team.json·미리알림)
  server.py     stdlib HTTP 서버 (127.0.0.1, /api/snapshot, /api/checkback)
  index.html    구조
  style.css     디자인 토큰·컴포넌트
  app.js        폴링·diff 렌더·디테일·체크백
  run.sh        실행 스크립트
```

## 데이터 소스 (전부 기존 자산, read-only)

- 팀 메일박스: `teams/<팀>/.claude/inbox/*.json`
- 팀 스킬: `teams/<팀>/.claude/skills/`
- 워커 스킬: `teams/<팀>/<워커>/.claude/skills/` (real dir만; symlink 공유 스킬 제외)
- 로스터: `.project/team.json`
- 미리알림: `reminders-team-bridge` 스킬(JXA)

스냅샷 diff 기준은 `.context/dashboard-prev.json`, 미리알림 캐시는 `.context/dashboard-reminders-cache.json`.

## 미리알림 체크백 (쓰기)

결정 디테일 패널 → `백로그에 기록`. **실데이터를 변경하므로 확인 다이얼로그**를 거친다(어느 목록·어느 작업·무슨 노트). `annotate`로 노트 append, 선택 시 `complete`로 완료 표시. 일괄 변경은 하지 않는다.
