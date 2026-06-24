# agent-project-template

재사용 가능한 **에이전트 프로젝트 템플릿**입니다. 새 프로젝트를 시작할 때 복사해서 쓰는 컴포넌트 계약 레이어로, 에이전트가 따르는 규칙(역할·입출력·작업 흐름)과 메모리·스킬·작업·MCP의 폴더 구조를 미리 고정해 둡니다. 특정 도메인·데이터셋·방법론에 묶이지 않은 중립 템플릿이며, 프로젝트별 내용은 이 템플릿을 가져다 쓰는 쪽에서 추가합니다. 기본 응답 언어는 한국어입니다.

## 폴더 구조

```text
agent-project-template/
├── AGENTS.md                  # 공유 계약: 에이전트 공통 규칙, 컴포넌트 역할, 입출력(I/O) 프로토콜
├── README.md                  # 이 문서
├── .mcp.json                  # 팀 공유 MCP 서버 정의 (Claude Code가 실제로 읽음, 기본 빈 목록)
├── .gitignore
└── .claude/
    ├── CLAUDE.md              # Claude 런타임 어댑터: AGENTS.md를 import하고 Claude 전용 실행 규칙 추가
    ├── settings.json          # 공유 설정 (플러그인, 권한, 훅 등)
    ├── settings.local.json    # 개인 설정 (git 미추적)
    ├── hooks/
    │   └── guard_word_json.py # word.json 직접 편집 차단 및 무결성 검증
    ├── memory/
    │   ├── memory.md          # 지속 컨텍스트·확정된 결정 (작업 로그 아님)
    │   ├── user_preferences.md# 프로젝트 범위의 안정적 선호
    │   └── word.json          # 용어 사전 (register-term 스킬로 관리)
    ├── skills/
    │   ├── skills.md          # 영어 스킬 색인 (프로젝트 훅이 자동 갱신)
    │   ├── _template/         # 새 스킬을 만들 때 복사하는 본보기
    │   ├── update-skill-index/# 스킬 색인 자동 재생성
    │   └── register-term/     # word.json 용어 등록·검증
    ├── tasks/
    │   └── tasks.md           # 현재 작업 패킷 (지속 메모리 아님)
    └── mcp/                   # MCP 서버 등록 관리 (정의 조각·운영 메모)
```

## 핵심 진입점

- **`AGENTS.md`** — 모든 에이전트가 먼저 읽는 공유 계약. 권한 순서, 정식 파일 경로, 컴포넌트별 입출력 규칙이 들어 있습니다.
- **`.claude/CLAUDE.md`** — Claude용 런타임 어댑터. `@../AGENTS.md`로 공유 계약을 시작 컨텍스트에 import하고, 읽기 순서와 실행 루프를 정의합니다.
- **`.claude/skills/skills.md`** — 사용 가능한 영어 스킬 색인. 스킬 본문은 트리거가 맞을 때만 엽니다.

## 포함된 스킬

| 스킬 | 역할 |
| --- | --- |
| `update-skill-index` | `skills/`를 스캔해 `skills.md`의 색인 표를 자동 재생성합니다. |
| `register-term` | 용어를 필수 4개 필드(`term`/`ko`/`definition`/`use_when`)로 검증해 `word.json`에 안전하게 등록합니다. |

## 자동화

`.claude/settings.json`에는 다음 공유 자동화가 설정되어 있습니다.

- Claude auto memory는 기본 비활성화되어 있습니다. 이 템플릿의 체크인된 `.claude/memory/`가 프로젝트 메모리의 기준입니다.
- `skills` 구성 변경 시 `ConfigChange` 훅이 영어 스킬 색인을 재생성합니다.
- `word.json`은 `Edit`/`Write`/`MultiEdit` 직접 편집을 막고, Bash 실행 후 `register-term --check`로 무결성을 재검증합니다.

## 사용 방법

1. 이 저장소를 새 프로젝트의 출발점으로 복사합니다.
2. `AGENTS.md`와 `.claude/CLAUDE.md`로 컴포넌트 계약을 확인합니다.
3. 프로젝트 고유 맥락은 `.claude/memory/`에, 작업은 `.claude/tasks/`에 기록합니다.
4. 반복되는 절차가 생기면 `.claude/skills/_template/`을 복사해 새 스킬을 만들고, 영어 색인은 프로젝트 훅이 자동 갱신합니다.
