# UMC 팀 관제 대시보드 (Textual TUI)

8개 tmux 창을 왔다갔다 하며 워커를 관리하던 것을 **한 터미널 화면**으로 모은다.
`.team/` 공유 store와 미리알림을 읽어 4분할로 보여준다.

## 단계 (0·1·2 모두 구현됨)

- **0단계 — 읽기**: 에이전트 그리드·미리알림 백로그·inbox 메시지 흐름·승격 후보를 한 화면에.
- **1단계 — 조작(CLI 위임)**: 미리알림 작업 추가, inbox 메시지 발행, 승격/거절 resolve.
- **2단계 — 에이전트 구동(tmux)**: 워커 카드에서 Claude를 tmux 새 윈도우로 구동·포커스·메시지 주입·인터럽트. 정체성(`CLAUDE_AGENT_NAME`)을 박아 유실 방지.

## 실행

**tmux 세션 안에서** 실행한다(2단계 워커 구동이 같은 세션의 새 윈도우를 쓴다):

```bash
tools/umc-dashboard/.venv/bin/python tools/umc-dashboard/app.py
```

구동된 워커는 `umc:<이름>` 윈도우 — `Ctrl-b <숫자>`로 대시보드↔워커를 오간다.

## 키

| 키 | 동작 | 대상 |
| --- | --- | --- |
| `↑↓ Enter` | 워커·후보 선택 | 사이드바·후보 큐 |
| `l` | 워커 구동(tmux) | 선택된 워커 |
| `f` | 그 워커 윈도우로 포커스 | 선택된 워커 |
| `m` | 메시지 주입 | 실행 중 워커 |
| `i` | 인터럽트(Esc) | 실행 중 워커 |
| `a` | 미리알림 작업 추가 | 백로그 |
| `p` | inbox 메시지 발행 | (선택 워커가 기본 수신자) |
| `P` / `D` | 승격 / 거절 | 선택된 후보 |
| `r` / `q` | 새로고침(자동 3초) / 종료 | — |

모달: `Ctrl-S` 확인 · `Esc` 취소.

## 설계 원칙

- **store가 진실원천**: `.team/`을 읽고, 쓰기는 검증된 기존 CLI(`reminders_bridge.py`·`team_inbox.py`·`detect_*.py`·`team_agent.py`)를 그대로 호출. 팀 로직 재구현 0.
- **얇은 뷰**: 위젯은 표시·버튼만, 로직은 CLI에 남긴다.
- **방어적 파싱**: atomic rename 중 반쯤 쓰인 파일을 만나도 크래시 대신 스킵.

## 구조

```
app.py            Textual App, 4분할 레이아웃 + 자동 새로고침
store.py          .team/ 읽기·파싱 (읽기 전용, 진실원천)
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

- **권한 실시간 게이트**: 파일 폴링이라 실시간 `canUseTool ask`를 못 받는다 → 권한 탭은 2단계(tmux/SDK) 이후.
- **미리알림 쓰기 충돌**: 사람이 미리알림 앱에서 동시 편집 가능 → 1단계에서 쓰기 전 `pull`로 최신 확인.
- **가용성**: 라이브 상태배지는 워커가 떠 있을 때만. store 파일은 항상 진실(워커가 죽어도 백로그·메시지는 보인다).
