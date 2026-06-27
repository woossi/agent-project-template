# UMC 팀 관제 대시보드 (Textual TUI)

여러 워커 상태를 왔다갔다 확인하던 것을 **한 터미널 화면**으로 모은다.
`.project/` 공유 store와 미리알림을 읽어 4분할로 보여준다.

## 단계 (0·1·2 모두 구현됨)

- **0단계 — 읽기**: 에이전트 그리드·미리알림 백로그·inbox 메시지 흐름·승격 후보를 한 화면에.
- **1단계 — 조작(CLI 위임)**: 미리알림 작업 추가, inbox 메시지 발행, 승격/거절 resolve.
- **2단계 — 에이전트 구동(headless)**: 대시보드 안에서 `claude -p` 세션을 워커별로 구동·응답 수신한다. 정체성(`CLAUDE_AGENT_NAME`)을 박아 유실 방지.

## 실행

```bash
tools/umc-dashboard/.venv/bin/python tools/umc-dashboard/app.py
```

## 키

| 키 | 동작 | 대상 |
| --- | --- | --- |
| `↑↓ Enter` | 워커·후보 선택 | 사이드바·후보 큐 |
| `c` | 선택 팀장에게 headless 지시 | 선택된 팀장 |
| `g` | 선택 워커의 팀 전체를 headless 구동 | 선택된 워커의 팀 |
| `A` | 일반 워커 상시구동 토글 | 전체 워커 |
| `x` | 선택 워커 세션 리셋 | 선택된 워커 |
| `a` | 미리알림 작업 추가 | 백로그 |
| `p` | 팀 mailbox 메시지 발행 | (선택 워커의 팀이 기본 수신 팀) |
| `P` / `D` | 승격 / 거절 | 선택된 후보 |
| `r` / `q` | 새로고침(자동 3초) / 종료 | — |

모달: `Ctrl-S` 확인 · `Esc` 취소.

## 설계 원칙

- **store가 진실원천**: `.project/`과 `teams/<팀>/`을 읽고, 쓰기는 검증된 기존 CLI(`reminders_bridge.py`·`team_inbox.py`·`detect_*.py`·`team_agent.py`)를 그대로 호출. 팀 로직 재구현 0.
- **얇은 뷰**: 위젯은 표시·버튼만, 로직은 CLI에 남긴다.
- **방어적 파싱**: atomic rename 중 반쯤 쓰인 파일을 만나도 크래시 대신 스킵.

## 구조

```
app.py            Textual App, 4분할 레이아웃 + 자동 새로고침
store.py          .project/ 읽기·파싱 (읽기 전용, 진실원천)
adapters.py       검증된 CLI subprocess 래퍼 (runner 주입 가능)
widgets/          AgentGrid · BacklogBoard · InboxTimeline · CandidateQueue
tests/            store 파싱 + adapters CLI 위임 (가짜 runner, 실데이터 미접촉)
```

## 환경

```bash
cd tools/umc-dashboard
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt pytest
```

## 테스트

```bash
tools/umc-dashboard/.venv/bin/python -m pytest tools/umc-dashboard/tests/ -q
```

## 미해결 (적대적 검증이 짚은 것)

- **권한 실시간 게이트**: 파일 폴링이라 실시간 `canUseTool ask`를 못 받는다 → 권한 탭은 별도 SDK 통합 이후.
- **미리알림 쓰기 충돌**: 사람이 미리알림 앱에서 동시 편집 가능 → 1단계에서 쓰기 전 `pull`로 최신 확인.
- **가용성**: 라이브 상태배지는 워커가 떠 있을 때만. store 파일은 항상 진실(워커가 죽어도 백로그·메시지는 보인다).
