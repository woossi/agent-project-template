# Team 공유 store (Model Y)

이 폴더는 **한 트리 + 정체성 N개**(Model Y) 팀의 공유 자산이다. peer 에이전트들은
Conductor 없이 **터미널 Claude**로 각자 실행되며, 같은 파일시스템의 이 store를 통해
조정한다. 서브에이전트(부모↔자식)가 아니라 동급(peer↔peer)이다.

## 구조

```
<Team 루트 = 이 저장소>
  .claude/                 # 공유 템플릿 1벌 (동일 구조가 자동 보장됨)
  .project/                   # ← 이 폴더: 공유 store (단일 소유)
     team.json             #   로스터·미리알림 바인딩·예산
     inbox/<수신자>/<msgid>.json   # 다대다 채널 (런타임, gitignore)
  agents/<이름>/           # 에이전트별 작업·.context (정체성으로 격리)
```

## 터미널에서 에이전트로 실행하기

각 터미널에서 **정체성만 다르게** 주고 같은 루트에서 실행한다:

```bash
# 터미널 1 — orchestrator
export CLAUDE_AGENT_NAME=orchestrator
claude

# 터미널 2 — worker-1
export CLAUDE_AGENT_NAME=worker-1
claude
```

`CLAUDE_AGENT_NAME`은 guard(`guard_agent_workspace.py`)와 받은 편지함이 모두 읽는
정체성이다. 설정하지 않으면 `main`으로 떨어져 정체성이 붕괴하므로 **반드시 export**한다.
`.claude/policies/agent-workspace.json`이 각 이름을 자기 작업 폴더로 한정하고
형제 폴더(`agents/<다른이름>/`)를 차단한다.

## 두 채널

| 채널 | 용도 | 도구 |
| --- | --- | --- |
| **미리알림 (목록=팀, 할일=Task)** | 사람도 보는 작업 백로그·진행상태 | `reminders-team-bridge` 스킬 |
| **받은 편지함 (`.project/inbox`)** | 에이전트끼리 구조화 메시지 | `team-inbox` 스킬 |

## 전형적 루프

1. orchestrator: `reminders_bridge.py pull umc` 로 백로그를 읽는다.
2. orchestrator: `team_inbox.py post --to worker-1 --subject "위임" --body "<할일 id> 맡아주세요"`.
3. worker-1: `team_inbox.py read` → 위임 확인 → `reminders_bridge.py annotate umc "[worker-1] 착수" --id <id>`.
4. worker-1: 완료 시 `reminders_bridge.py complete umc --id <id>` → `team_inbox.py post --to orchestrator --subject "완료" --body "<id> done"`.
5. 양쪽 모두 처리한 메시지는 `team_inbox.py ack --id <msgid>`.

미리알림 접근은 자동화(TCC) 권한이 필요하다(`reminders-team-bridge` 참조).
