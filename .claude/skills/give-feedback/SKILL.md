# 스킬: give-feedback

## 사용 시점

상대 에이전트(doc-knowledge-curator)의 산출물을 검토하고 품질 피드백을 보낼 때. 구체적으로:

- 상대가 Vault에 정착시킨 노트·frontmatter·링크 구조에서 문제(깨진 출처, 누락 메타데이터, 잘못된 분류 등)를 발견했을 때.
- 상대 산출물이 좋아서 그 패턴을 강화하도록 칭찬을 남기고 싶을 때.
- 상대에게 산출물 변경을 요청하거나 질문해야 할 때.

근거 없이 인상만으로 피드백하지 않는다. 메시지의 근거는 상대 산출물 안에 실제로 있어야 한다.

## 목적

상대 받은편지함(`.context/feedback/inbox.jsonl`)에 근거 있는 피드백 한 건을 안전하게 append 하고, 내 `outbox.jsonl`에 사본을 남긴다. 두 작업을 `record-feedback` 한 번으로 처리한다.

## 입력

- `task_ref` — 상대가 만든 산출물 경로 또는 상대 task signature 슬러그.
- `kind` — `praise` | `issue` | `request_change` | `question` 중 하나(`.claude/policies/feedback.json`의 `kinds`).
- `severity` — `info` | `minor` | `major` | `critical` 중 하나(`severity_order`). 기본 `minor`.
- `message` — 근거가 담긴 한 문장.
- `related_paths`(선택) — 상대 프로젝트 기준 관련 경로들.
- 라우팅 설정: `.claude/policies/feedback.json`의 `agent.peer` / `agent.peer_inbox` (수정 불필요, 자동 사용).

## 절차

1. **대상과 근거를 확정한다.** 어떤 산출물(`task_ref`)에 대한 피드백인지, 근거가 산출물 어디에 있는지 분명히 한다. 모호하면 보내지 않는다.
2. **kind와 severity를 판단한다.** kind와 severity가 서로 모순되지 않게 한다(예: `praise`에 `critical` 금지).
3. **피드백을 보낸다:**
   ```bash
   python3 .claude/hooks/detect_feedback.py record-feedback \
     --task-ref "<상대 산출물/시그니처>" \
     --kind "<praise|issue|request_change|question>" \
     --severity "<info|minor|major|critical>" \
     --message "<근거 있는 한 문장>" \
     --related-paths "<p1,p2>" \
     --session "$CLAUDE_SESSION_ID"
   ```
4. **확인한다:** 명령이 종료코드 0이고, 상대 inbox와 내 `outbox.jsonl`에 같은 `id`로 한 건씩 들어갔는지 본다.
5. 보낸 피드백(`id`, `to_agent`, 경로)을 사용자에게 보고한다.

## 출력 형식

상대 `.context/feedback/inbox.jsonl`과 내 `.context/feedback/outbox.jsonl`에 동일 레코드 한 줄이 append 된다. 레코드:

```json
{"id":"fb-<sha1_12>","ts":1750000000,"from_agent":"research-assistant","to_agent":"doc-knowledge-curator","kind":"request_change","severity":"major","task_ref":"summarize-vault-note","message":"요약 노트의 출처 링크가 깨졌다","related_paths":["knowledge/notes/x.md"],"session":"s-abc","status":"open"}
```

`id`는 내용 기반 sha1이라 같은 피드백을 다시 보내도 동일하다(수신측이 중복으로 표면화하지 않는다).

## 품질 점검

- `message`에 검증 가능한 근거가 들어 있다(막연한 비난·칭찬 금지).
- `kind`와 `severity`가 모순되지 않는다.
- 명령 종료코드 0, 상대 inbox와 내 outbox에 각각 한 건.

## 자주 발생하는 실패 사례

- **`error: policy agent.peer_inbox is not set`** → `.claude/policies/feedback.json`의 `agent.peer_inbox`가 상대 inbox 절대경로를 가리키는지 확인한다.
- **`error: --kind must be one of [...]`** → 정책 `kinds`에 있는 값만 쓴다.
- **상대 inbox 쓰기 차단** → 작업 경계(`agent-workspace.json`)의 `defaults.allow`에 상대 inbox 경로가 있어야 한다. 이 스킬은 `record-feedback`으로만 상대 받은편지함에 쓴다.
- **근거 없는 모호한 피드백** → 금지. 절차 1단계로 돌아가 산출물에서 근거를 찾는다.
