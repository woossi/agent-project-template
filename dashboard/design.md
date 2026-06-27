# team-umc 거버넌스 대시보드 — Design

> Apple Human Interface Guidelines × Claude 디자인 언어로 설계한, **팀장급 결정·거버넌스 이벤트 전용** 로컬 웹 대시보드.
> 목적: 14 peer 에이전트의 개별 워커 버퍼를 보지 않고도, 팀장의 **팀 단위 자원·에이전트 추가·스킬 추가**와 **워커 스킬 업데이트 소식**만 한눈에 본다.
> 제약: 터미널 TUI와 **완전히 분리된 별도 프로세스**(로컬 웹). TUI 멈춤·렉을 일으키지 않는다.

---

## 1. 설계 원칙 (Design Principles)

이 대시보드는 "조율자의 관제탑"이다. 사용자는 orchestrator처럼 **결정과 거버넌스의 흐름**만 보고, 실행 디테일(워커 버퍼)은 보지 않는다.

| 원칙 | 적용 |
| --- | --- |
| **Clarity (Apple)** | 정보 위계가 시각 위계와 일치한다. 팀장 결정 > 거버넌스 변화 > 진행상태 순으로 크기·대비·위치가 줄어든다. |
| **Deference (Apple)** | UI 크롬은 물러나고 콘텐츠(결정·소식)가 주인공. 장식 0, 그림자·테두리 최소. |
| **Depth (Apple)** | 레이어(팀 카드 → 이벤트 → 디테일)는 z축 elevation과 부드러운 전환으로 표현. |
| **Warmth (Claude)** | 차갑지 않은 중립. Claude의 따뜻한 코럴(crail/clay) 액센트를 결정·주의 지점에만 절제해 쓴다. |
| **Legibility first** | 모든 텍스트는 한국어 본문 가독 우선. 시스템 폰트 스택. 최소 13px. |
| **No lag by construction** | 폴링은 클라이언트가 하고(10초), 백엔드는 stateless 스냅샷만 제공. 터미널과 0 결합. |

---

## 2. 디자인 토큰 (Design Tokens)

### 2.1 색 (Color) — Light/Dark 자동 (prefers-color-scheme)

Claude 따뜻한 중립 + Apple 시스템 액센트.

```
/* Light */
--bg-canvas:      #F5F4F2;   /* Claude 따뜻한 오프화이트 (회색 아님) */
--bg-surface:     #FFFFFF;   /* 카드 표면 */
--bg-surface-2:   #FAF9F7;   /* 중첩 표면 */
--border-hair:    rgba(0,0,0,0.08);   /* 헤어라인 (Apple separator) */
--text-primary:   #1A1A18;   /* 거의 검정, 살짝 따뜻 */
--text-secondary: #6B6962;   /* 보조 */
--text-tertiary:  #9B998F;   /* 메타·타임스탬프 */

--accent-claude:  #C96442;   /* Claude 코럴 — 결정·CTA */
--accent-claude-soft: #F4E5DE; /* 코럴 배경 틴트 */

/* 상태색 (Apple semantic, 채도 낮춤) */
--ok:    #3A8A5F;   /* PASS·완료 */
--warn:  #C8881A;   /* PARTIAL·주의 */
--fail:  #C0473A;   /* FAIL·차단 */
--info:  #3B6EA8;   /* 정보·진행 */

/* 팀 색 (5팀 식별, 저채도 파스텔 — 점/링에만) */
--team-data:     #5B8DBE;
--team-write:    #8A6FB0;
--team-scout:    #5FA8A0;
--team-review:   #C28A3E;
--team-analysis: #B0708A;

/* Dark (prefers-color-scheme: dark) */
--bg-canvas-d:    #1A1917;
--bg-surface-d:   #242220;
--border-hair-d:  rgba(255,255,255,0.10);
--text-primary-d: #F2F0EC;
```

### 2.2 타이포 (Type) — Apple 시스템 폰트 스택

```
--font-sans: -apple-system, "SF Pro Text", "Pretendard", "Apple SD Gothic Neo", system-ui, sans-serif;
--font-mono: "SF Mono", "JetBrains Mono", ui-monospace, monospace;
```

| 역할 | 크기/굵기/자간 | 용도 |
| --- | --- | --- |
| Display | 28 / 700 / -0.02em | 대시보드 타이틀 |
| Title | 20 / 650 / -0.01em | 섹션 헤더 |
| Headline | 16 / 600 | 팀 카드 제목·결정 제목 |
| Body | 14 / 400 / 1.5 | 결정 본문·소식 |
| Caption | 12 / 500 | 배지·메타 |
| Mono-meta | 12 / 450 | 타임스탬프·msgid·해시 |

### 2.3 공간·모양 (Spacing & Shape)

- 8pt 그리드: `4 / 8 / 12 / 16 / 24 / 32 / 48`.
- 둥근모서리: 카드 `16px`, 배지/칩 `8px`, 버튼 `10px` (Apple continuous corner 느낌).
- 그림자: 1단계만. `0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)`. dark는 그림자 대신 border elevation.

### 2.4 모션 (Motion)

- 전환 `180ms cubic-bezier(0.32, 0.72, 0, 1)` (Apple ease). 새 이벤트 입장 = fade+8px up.
- 폴링 갱신은 **깜빡임 없이** diff 패치(새 항목만 입장 애니메이션). 전체 리렌더 금지(렉·점프 방지).
- `prefers-reduced-motion` 존중 → 전환 0.

---

## 3. 정보 구조 (Information Architecture)

```
┌─ Header ────────────────────────────────────────────────┐
│  team-umc · 거버넌스 관제탑          ◷ 10s · ● live      │
├─ Reminders Strip (미리알림 백로그 요약) ─────────────────┤
│  umc 8/36 open  · umc-data 4/6 · umc-write 1/1 · …       │
├─ Team Lanes (5팀 카드 그리드) ──────────────────────────┤
│  ┌ data ─────┐ ┌ write ────┐ ┌ scout ───┐               │
│  │ ●팀장상태 │ │           │ │          │  …            │
│  │ +스킬 1   │ │ +스킬 0   │ │          │               │
│  │ +에이전트0│ │ +에이전트0│ │          │               │
│  │ 최근결정▸ │ │ 최근결정▸ │ │          │               │
│  └───────────┘ └───────────┘ └──────────┘               │
├─ Decision Feed (팀장 결정·거버넌스 타임라인) ───────────┤
│  ● write-lead  register-term 12 승인          2분 전     │
│  ● review-lead T-RV-01 배분                   5분 전     │
│  ⚑ data-lead   verdict FAIL ×1 (2연속 신호)   8분 전     │
├─ Skill & Agent News (스킬/에이전트 변화 소식) ──────────┤
│  ＋ data 팀스킬 'data-artifact-pipeline' 추가            │
│  ↻ mw register-term symlink 복구                          │
└─────────────────────────────────────────────────────────┘
```

**핵심 결정**: 사용자는 **개별 워커 버퍼를 보지 않는다.** 화면 4개 영역은 전부 **팀장급 산출(결정·할당·verdict)**과 **거버넌스 변화(스킬·에이전트 추가, 워커 스킬 업데이트 소식)**만 담는다.

---

## 4. 컴포넌트 명세 (Components)

전 구성요소가 빠짐없이 들어간다. 각 컴포넌트는 데이터 소스와 1:1로 묶인다.

### 4.1 Header
- 좌: 타이틀 `team-umc · 거버넌스 관제탑`.
- 우: 폴링 표시기(`◷ 10s`) + live dot(백엔드 도달 가능 시 초록, 실패 시 회색). 클릭 시 수동 새로고침.

### 4.2 Reminders Strip — *미리알림 연동(읽기, 회사 전체)*
- 데이터: `reminders_bridge.py list-teams` → 회사 전체 `umc` 목록만 상단 스트립에 둔다.
- 표시: `open/total` 칩. open>0면 코럴 점.
- 팀별 목록(`umc-data`…)은 상단이 아니라 **각 팀 카드 안**에 표시한다(§4.3, 사용자 결정 2026-06-28) — 팀 단위 자원의 일부로 보기 위함.

### 4.3 Team Lane Card (×5) — *팀장의 팀 단위 자원*
한 팀 = 한 카드. 사용자가 명시한 "개별 팀장의 팀 단위 자원·에이전트 추가·스킬 추가 여부"의 1차 표면.

| 슬롯 | 내용 | 소스 |
| --- | --- | --- |
| 헤더 | 팀명 + 팀색 링 + 팀장 이름 | `team.json subteams` |
| 멤버 | 워커 수 / 워커 이름 칩 | `team.json members` |
| **＋스킬** | 팀 스킬 개수 + 최근 추가 N | `teams/<팀>/.claude/skills/` 스캔 |
| **＋에이전트** | 워커(에이전트) 수 + 최근 추가 | `team.json` diff (이전 스냅샷 대비) |
| 최근 결정 | 팀장 최신 결정 1줄 ▸ | 메일박스 `from=<팀>-lead` 최신 |
| verdict | PASS/PARTIAL/FAIL 미니 배지 | 메일박스 `verdict` 필드 |
| **미리알림** | 자기 팀 목록(`umc-<팀>`) `open/total` | `reminders_bridge` + `team.json reminders_list` |

### 4.4 Decision Feed — *팀장급 결정 타임라인*
- 데이터: 전 팀 메일박스 메시지 중 **발신자가 lead/orchestrator**인 것 + `verdict`/`quality_gate` 있는 것.
- 행: `● <발신팀장> · <subject 요약> · <상대시간>`. 차단/실패는 `⚑` + fail색.
- 정렬: `ts_ns` 내림차순(서버 `_scan_mailboxes`에서 정렬). 서버가 최신 60건으로 캡해 전달하므로 클라이언트는 단일 패스로 렌더(60건 한도에서 페인트 폭주 없음).
- 클릭: 본문(body) 디테일 패널 슬라이드인(우측). **결정의 근거·완료기준까지.**
- 사용자가 명시한 "어떤 스킬이 관리되는지 등 팀장급 결정 결과"의 메인 채널.

### 4.5 Skill & Agent News — *스킬/에이전트 변화 소식*
사용자 명시: "개별 팀장의 스킬 추가 여부가 중요" + "개별 워커의 스킬 업데이트도 소식화".
- `＋` 팀 스킬 추가: `teams/<팀>/.claude/skills/` 신규 디렉토리.
- `＋` 에이전트 추가: `team.json members` 증가.
- `↻` 워커 스킬 업데이트: 워커 폴더 스킬 mtime 변화 → "소식" 카드(상세 아님, **한 줄 소식**).
- `★` 승격/파생 신호: `detect_team_promotions.py` 후보(있으면).
- 각 소식 = 칩 1개. 클릭 시 무엇이 바뀌었는지 1줄 설명.

### 4.6 Decision Detail Panel (slide-in)
- 메일박스 1건의 full body + 메타(from/to_team/work_ref/reply_to 체인).
- **미리알림 체크백 액션**(아래 4.7)이 여기 붙는다.

### 4.7 Reminder Check-back Action — *미리알림 연동(쓰기)*
사용자 결정: "읽기+결정 체크백 쓰기."
- 결정 디테일 패널에서 `이 결정을 umc 백로그에 기록` 버튼.
- 동작: 관련 미리알림 작업(work_ref 매칭)에 `annotate`로 진행상태·결정 노트 append. 또는 완료 결정이면 `complete`.
- **안전장치**: 쓰기 전 확인 다이얼로그(어느 목록·어느 작업·무슨 노트). 실데이터 변경이므로 명시 컨펌. 일괄 변경 금지.

### 4.8 Empty / Error States
- 백엔드 미도달: live dot 회색 + "스냅샷을 불러올 수 없음 · 재시도".
- 이벤트 0: "조용합니다 — 새 팀장 결정이 없습니다." (중립 일러스트 없이 텍스트만, deference).

---

## 5. 아키텍처 (Architecture) — 렉 0 보장

```
┌─ 브라우저 (별도 프로세스) ──────────┐      ┌─ 터미널 TUI (영향 0) ─┐
│  index.html + app.js + style.css    │      │  14 peer 세션          │
│  - 10s setInterval fetch            │      │  (전혀 건드리지 않음)  │
│  - diff 패치 렌더 (점프 없음)        │      └────────────────────────┘
└──────────────┬──────────────────────┘
               │ GET /api/snapshot (stateless)
┌──────────────▼──────────────────────┐
│  server.py (Python stdlib http)      │
│  - scan.py 호출 → JSON 스냅샷         │
│  - POST /api/checkback → reminders    │
└──────────────┬──────────────────────┘
               │ read-only 스캔
┌──────────────▼──────────────────────┐
│  데이터 소스 (기존 자산)              │
│  · teams/*/.claude/inbox/*.json       │
│  · teams/*/.claude/skills/            │
│  · teams/*/<워커>/.claude/skills/      │
│  · .project/team.json                 │
│  · reminders_bridge.py (JXA)          │
└──────────────────────────────────────┘
```

**렉이 없는 이유**:
1. 대시보드는 **별도 OS 프로세스**(Python http 서버 + 브라우저). 터미널 렌더 루프와 메모리·이벤트 루프를 공유하지 않는다.
2. 백엔드는 **stateless**: 매 요청마다 디스크 스냅샷만 읽고 반환(상주 워처 없음 → 파일 I/O 폭주 없음).
3. 폴링은 **클라이언트 타이머**(10초). 서버 푸시·웹소켓 없음(단순·견고).
4. 렌더는 **diff 패치**: 새 이벤트만 DOM 입장. 전체 innerHTML 교체 금지 → 스크롤 점프·페인트 폭주 없음.
5. reminders JXA 호출은 **요청 시에만**(폴링 경로에서 제외, 별도 가벼운 캐시 + 명시 새로고침) → osascript 비용이 폴링을 막지 않음.

---

## 6. 데이터 계약 (Snapshot JSON)

`GET /api/snapshot` 반환:

```json
{
  "generated_ts_ns": 0,
  "teams": [
    { "name": "data", "color": "var(--team-data)", "lead": "data-lead",
      "members": ["data-engineer","data-curator","inference-runner","data-lead"],
      "team_skills": ["data-artifact-pipeline"],
      "team_skill_added_recent": 1,
      "agent_added_recent": 0,
      "latest_decision": { "id":"…", "subject":"…", "ts_ns":0 },
      "verdict": { "result":"FAIL", "count":1 } }
  ],
  "decisions": [
    { "id":"…", "from":"write-lead", "team":"write", "subject":"…",
      "body":"…", "ts_ns":0, "verdict":null, "quality_gate":null,
      "work_ref":"…", "reply_to":"…" }
  ],
  "news": [
    { "kind":"team_skill_added", "team":"data", "name":"data-artifact-pipeline", "ts_ns":0 },
    { "kind":"worker_skill_updated", "team":"write", "worker":"manuscript-writer", "name":"register-term", "ts_ns":0 },
    { "kind":"agent_added", "team":"analysis", "name":"…", "ts_ns":0 },
    { "kind":"promotion_signal", "team":"write", "detail":"…", "ts_ns":0 }
  ],
  "reminders": [
    { "list":"umc", "open":8, "total":36 },
    { "list":"umc-data", "open":4, "total":6 }
  ]
}
```

`POST /api/checkback` 입력: `{ "list":"umc", "task_id_or_name":"…", "note":"…", "complete":false }` → reminders_bridge `annotate`/`complete` 호출, 결과 JSON 반환.

---

## 7. 접근성 (Accessibility)

- 색만으로 상태 구분 금지 → PASS/FAIL은 색 + 아이콘(`✓`/`⚑`) + 레이블 병행.
- 키보드: feed 행 `Tab` 포커스, `Enter`로 디테일, `Esc`로 닫기.
- `aria-live="polite"`로 새 결정 소식 스크린리더 통지(폭주 방지 polite).
- 대비: 본문 텍스트 ≥ 4.5:1, 메타 ≥ 3:1.
- `prefers-reduced-motion`·`prefers-color-scheme` 존중.

---

## 8. 비범위 (Out of Scope)

- 개별 워커 버퍼/터미널 출력 표시 (← 명시적으로 **안 함**: 렉·소음의 원인).
- 워커에게 명령 전송·작업 할당 (대시보드는 **읽기 + 미리알림 체크백**만; 조율은 orchestrator 세션이 함).
- 인증·다중 사용자 (로컬 단일 사용자 전제, 127.0.0.1 바인드).
```
