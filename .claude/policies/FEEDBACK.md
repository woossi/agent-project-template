# Inter-Agent Feedback (에이전트 간 작업 피드백)

두 로컬 에이전트 프로젝트가 서로의 산출물 품질에 대한 피드백을 주고받아 각자의 품질 관리에
반영하는 양방향 루프입니다. 기존 `Tasks → Skills → Agents` 승격 사슬, `Memory → 선호/용어`
파생 사슬과 같은 패턴(결정적 트리거 hook + 정책 JSON 임계값 + 판단 저작 스킬 + resolve로 닫기)을
따릅니다.

## 무엇이 들어 있나

| 파일 | 역할 |
| --- | --- |
| `.claude/hooks/detect_feedback.py` | 송신(`record-feedback`)·재표면화(hook)·닫기(`resolve`)·검증(`evaluate`)을 모두 담은 hook. self/peer를 정책에서 읽으므로 **모든 에이전트가 동일 파일**을 쓴다 |
| `.claude/policies/feedback.json` | 라우팅(self/peer/peer_inbox)과 임계값(max_open, min_severity, 재발 신호) 정책 |
| `.claude/skills/give-feedback/` | 상대 산출물을 검토해 근거 있는 피드백을 보내는 스킬 |
| `.claude/skills/process-feedback/` | 받은 피드백을 처리하고 승격·파생 사슬에 연결한 뒤 닫는 스킬 |
| `.claude/hooks/tests/test_detect_feedback.py` | 단위 테스트 |

settings.json의 `PostToolUse`·`SessionStart`에 `detect_feedback.py`가 등록되어, 받은편지함의 open
피드백을 매 턴·세션 시작마다 `additionalContext`로 재표면화합니다.

## 동작 원리

```
  에이전트 A                                        에이전트 B
  ┌─────────────────┐                              ┌─────────────────┐
  │ give-feedback   │  record-feedback             │                 │
  │   스킬          │ ───────────────────────────▶ │ B/.context/     │
  │                 │  (B inbox에 직접 append)     │  feedback/      │
  │ A/.context/     │ ◀─────────────────────────── │  inbox.jsonl    │
  │  feedback/      │   B의 give-feedback          │                 │
  │   inbox.jsonl   │                              │ SessionStart/   │
  │   outbox.jsonl  │                              │  PostToolUse    │
  └─────────────────┘                              │  hook이 재표면화 │
                                                   │       ↓         │
                                                   │ process-feedback│
                                                   │   스킬이 처리·  │
                                                   │   record-task / │
                                                   │   record-signal │
                                                   │   → resolve     │
                                                   └─────────────────┘
```

- A가 B에게 피드백을 보내면 **B의 `inbox.jsonl`에 직접 append**되고, A의 `outbox.jsonl`에 사본이
  남습니다. 한 번의 `record-feedback`이 두 곳에 씁니다.
- B의 hook이 자기 inbox의 open 피드백을 평가해 `candidates.json`에 쓰고 재표면화합니다.
- B는 `process-feedback` 스킬로 처리하고, 처리 작업을 `task_ledger.py record-task`로 남겨
  **승격 사슬**에 연결하며, 반복 패턴은 `detect_derivations.py record-signal --kind preference`로
  **선호 파생**에 연결합니다. 마지막에 `resolve`로 닫으면 재표면화가 멈춥니다.

레코드는 `.context/feedback/`(git-ignore, transient)에 append-only로 쌓이고, `id`(내용 기반
sha1)로 중복이 접힙니다. 상태 변경도 새 줄로 append되어 수신측이 id별 last-write-wins로 fold합니다.

## 두 에이전트 페어링 설정 (필수 4단계)

이 템플릿으로 만든 두 프로젝트 A, B를 피드백으로 잇습니다. 각 프로젝트에서:

### 1. `feedback.json`의 `agent` 블록 채우기

A 프로젝트 `.claude/policies/feedback.json`:
```json
"agent": {
  "self": "<A 에이전트명>",
  "peer": "<B 에이전트명>",
  "peer_inbox": "<B 프로젝트 절대경로>/.context/feedback/inbox.jsonl"
}
```
B 프로젝트에서는 self/peer/peer_inbox를 **반대로** 채웁니다(self=B, peer=A, peer_inbox=A의 inbox).

### 2. `agent-workspace.json`의 `defaults.allow`에 상대 inbox 한 줄 추가

A 프로젝트:
```json
"allow": [ ".", "<B 프로젝트 절대경로>/.context/feedback/inbox.jsonl" ]
```
**상대 inbox 파일 하나만** 허용합니다(outbox/candidates/decisions 등은 추가하지 않음 — 받은편지함
투입구만 뚫는 좁힘 원칙). B 프로젝트에서는 A의 inbox 경로를 추가합니다.

### 3. `AGENTS.md`의 작업 경계에 같은 경로와 제약 문장 기입

```
허용 작업 경로:
- .
- <상대 프로젝트>/.context/feedback/inbox.jsonl (<상대 에이전트명> 받은편지함; 피드백 append 전용)

상대 에이전트 받은편지함은 record-feedback으로만 append 한다. 그 외 상대 프로젝트 경로는 읽기·쓰기 모두 금지한다.
```

### 4. settings.json 확인

`detect_feedback.py`는 이미 `PostToolUse`·`SessionStart`에 등록되어 있습니다(템플릿 기본 포함).
추가 작업 없음.

## 사용법

피드백 보내기:
```bash
python3 .claude/hooks/detect_feedback.py record-feedback \
  --task-ref "<상대 산출물/시그니처>" \
  --kind "<praise|issue|request_change|question>" \
  --severity "<info|minor|major|critical>" \
  --message "<근거 있는 한 문장>" \
  --related-paths "<p1,p2>" --session "$CLAUDE_SESSION_ID"
```

받은 피드백 확인·닫기:
```bash
python3 .claude/hooks/detect_feedback.py evaluate          # open 목록
python3 .claude/hooks/detect_feedback.py resolve --id <fb-...> --decision resolved --reason "..."
```

자세한 절차는 `give-feedback` / `process-feedback` 스킬을 참고하세요.

## 정책 조정

`feedback.json`에서:
- `surface.max_open` — 한 번에 재표면화할 open 피드백 최대 수.
- `surface.min_severity` — 이 미만 severity는 재표면화에서 제외(기본 `minor`이라 `info`는 제외).
- `surface.recurrence_signal` — 같은 `task_ref`+`kind`가 몇 회/몇 세션 반복되면 `[recurring]`으로
  표시해 선호 파생을 유도할지.
- `kinds` / `severity_order` — 허용 종류와 severity 등급(정렬·필터에 사용).

## 검증

```bash
cd .claude/hooks/tests && python3 -m unittest test_detect_feedback
```

E2E: A에서 `record-feedback`으로 B inbox에 쓰고, B 세션 시작 시 재표면화되는지, `resolve` 후
사라지는지 확인합니다. 가드 음성 테스트로 상대 inbox 외 경로 쓰기가 차단되는지도 확인하세요.

## 설계 노트 / 제약

- 피드백은 `.context/`(git-ignore)에 쌓여 **커밋되지 않습니다**(transient 받은편지함). 영속 기록이
  필요하면 `feedback.json`에 `"archive"` 경로를 추가하고 resolve 시 archive로 append하도록
  확장하세요(기본 미포함).
- hook은 append-only·멱등·에러 삼킴·exit 0 규약을 따릅니다. 임계값은 코드가 아니라 정책에서만
  조정합니다.
- 외부 원본(예: Vault·문헌 PDF)은 수정하지 않습니다. 쓰기는 상대 `.context/feedback/inbox.jsonl`로만.
