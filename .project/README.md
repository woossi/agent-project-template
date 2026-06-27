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
     goals/                #   팀 목표
     memory/ · word.json   #   회사 단위 장기 결정·용어
  teams/<팀>/.claude/inbox/       # 팀 mailbox (런타임, gitignore)
  teams/.orchestrator/inbox/      # 총괄 mailbox (런타임, gitignore)
  teams/<팀>/<워커>/        # 워커별 작업·.context (정체성으로 격리)
```

## 터미널에서 에이전트로 실행하기

각 터미널에서 **정체성만 다르게** 주고 같은 루트에서 실행한다:

```bash
# 터미널 1 — orchestrator
export CLAUDE_AGENT_NAME=orchestrator
claude

# 터미널 2 — data-engineer
export CLAUDE_AGENT_NAME=data-engineer
cd teams/data/data-engineer && claude
```

`CLAUDE_AGENT_NAME`은 guard(`guard_agent_workspace.py`)와 받은 편지함이 모두 읽는
정체성이다. 설정하지 않으면 `main`으로 떨어져 정체성이 붕괴하므로 **반드시 export**한다.
`.claude/policies/agent-workspace.json`이 각 이름을 자기 작업 폴더로 한정하고
형제 폴더(`teams/<팀>/<다른워커>/`)를 차단한다.

## 두 채널

| 채널 | 용도 | 도구 |
| --- | --- | --- |
| **미리알림 (목록=팀, 할일=Task)** | 사람도 보는 작업 백로그·진행상태 | `reminders-team-bridge` 스킬 |
| **팀 mailbox (`teams/<팀>/.claude/inbox`)** | 팀 간 구조화 메시지와 팀장 수신함 | `team-inbox` 스킬 |

## 전형적 루프

1. 작업 요청자는 `team_inbox.py post --to-team <팀> --subject "위임" --body "<요청>"`으로 팀 mailbox에 투입한다.
2. 팀장만 `team_inbox.py read --team <팀>` 및 `claim/ack`를 수행한다.
3. 팀장은 팀 보드(`teams/<팀>/.claude/tasks/tasks.md`)에 워커별 작업을 기록한다.
4. 워커는 팀 보드의 자기 섹션을 읽고 수행한다. mailbox는 직접 읽지 않는다.
5. 워커는 완료/질문을 `team_inbox.py post --to-team <팀>` 또는 필요한 상대 팀으로 보고한다.

`teams/.orchestrator/inbox/`는 총괄 전용 mailbox다. 누구나 post는 할 수 있지만 read/claim/ack는 `orchestrator`만 한다.

미리알림 접근은 자동화(TCC) 권한이 필요하다(`reminders-team-bridge` 참조).
