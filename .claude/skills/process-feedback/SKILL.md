# 스킬: process-feedback

## 사용 시점

받은편지함에 들어온 피드백이 SessionStart 또는 PostToolUse hook(`detect_feedback.py`)에 의해 재표면화됐을 때. 구체적으로:

- 세션 시작 시 "Inbound feedback is open ..." 안내가 떴을 때.
- `.context/feedback/candidates.json`에 open 피드백 항목이 있을 때.

받은 피드백을 처리해 내 작업·품질에 반영하고, 그 처리를 기존 스킬·메모리 승격 사슬과 연결한 뒤 항목을 닫는다.

## 목적

받은 피드백을 (1) 실제로 처리하고, (2) 처리 작업을 task ledger에 남겨 반복 시 스킬/에이전트 승격으로 잇고, (3) 반복되는 피드백 패턴은 선호 파생 후보로 올리고, (4) 항목을 resolve 해 재표면화를 멈춘다.

## 입력

- `.context/feedback/candidates.json` — 평가된 open 피드백 목록(각 항목: `id`, `from_agent`, `feedback_kind`, `severity`, `task_ref`, `message`, `related_paths`, `recurring`).
- 라우팅·임계값 설정: `.claude/policies/feedback.json`.

## 절차

1. **open 항목을 읽는다:** `.context/feedback/candidates.json`의 `feedback` 배열을 확인한다(또는 `python3 .claude/hooks/detect_feedback.py evaluate`로 갱신·확인).
2. **각 항목을 처리한다.** `message`의 근거를 산출물에서 확인하고, 타당하면 해당 작업(노트 수정, 출처 보강, 분류 교정 등)을 수행한다. 타당하지 않으면 decline 사유를 정한다.
3. **(a) 처리 작업을 task ledger에 남긴다** — 반복 시 스킬/에이전트 승격으로 연결된다:
   ```bash
   python3 .claude/hooks/task_ledger.py record-task \
     --signature "<task_ref 슬러그>" \
     --objective "피드백 반영: <무엇을 했는지>" \
     --paths "<수정한 경로들>" \
     --session "$CLAUDE_SESSION_ID"
   ```
4. **(b) `[recurring]` 표시가 붙은 반복 패턴은 선호 파생 후보로 올린다:**
   ```bash
   python3 .claude/hooks/detect_derivations.py record-signal \
     --kind preference --key "<선호 슬러그>" \
     --note "<상대가 반복 지적한 안정적 선호>" \
     --session "$CLAUDE_SESSION_ID"
   ```
5. **항목을 닫는다:**
   ```bash
   python3 .claude/hooks/detect_feedback.py resolve \
     --id "<fb-...>" --decision resolved --reason "<반영 내용>" \
     --session "$CLAUDE_SESSION_ID"
   ```
   - 반영하지 않기로 했으면 `--decision decline --reason "<사유>"`.
   - 일단 접수만 표시하려면 `--decision ack`(open 상태 유지, 재표면화는 계속됨).
6. **검증한다:** `python3 .claude/hooks/detect_feedback.py evaluate --check`가 종료코드 0(남은 open 없음)인지 확인한다.
7. 처리·승격·resolve 결과를 사용자에게 보고한다.

## 출력 형식

- 처리한 산출물 변경(이 프로젝트 산출물 또는 노트).
- `.context/task-log/tasks.jsonl`에 record-task 한 줄(반복 시 `detect_promotions`가 승격 후보로 띄움).
- `[recurring]` 항목에 대해 `.context/memory-log/signals.jsonl`에 선호 신호 한 줄.
- `.context/feedback/decisions.json`에 `{id: {decision, reason}}`, `.context/feedback/inbox.jsonl`에 상태 갱신 줄.
- `.context/feedback/candidates.json`에서 닫힌 항목이 사라짐.

## 품질 점검

- 처리한 모든 open 항목이 resolve(또는 decline) 되어 candidates에서 사라진다 — `evaluate --check` 종료코드 0.
- 실제 반영 작업이 `record-task`로 남아 승격 사슬에 연결됐다.
- `[recurring]` 패턴 중 안정적 선호인 것은 `record-signal --kind preference`로 후보화됐다.

## 자주 발생하는 실패 사례

- **resolve 후에도 항목이 다시 뜸** → `--decision ack`로 닫으면 open이 유지된다. 처리 완료면 `resolved`, 미반영이면 `decline`을 쓴다.
- **승격 사슬과 단절** → 피드백을 처리만 하고 `record-task`를 빠뜨리면 반복돼도 스킬로 승격되지 않는다. 3단계를 생략하지 않는다.
- **선호를 임의로 지어냄** → 금지. `[recurring]`이고 안정적 선호로 확신될 때만 record-signal 한다. 파생 후보가 뜨면 `user_preferences.md` 기입은 별도 판단 단계다.
- **근거 없이 무조건 반영** → 금지. `message`의 근거를 산출물에서 확인한 뒤 처리하고, 부당하면 `decline`한다.
