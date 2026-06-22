# MCP 서버 등록 관리

이 폴더는 프로젝트에서 사용하는 **MCP 서버 등록을 관리**하는 곳입니다. 실제 서버 정의는 프로젝트 루트의 `.mcp.json`에 들어가며, 이 폴더에는 서버별 설명·예시·운영 메모를 둡니다.

## 구조

- 프로젝트 루트 `.mcp.json` — Claude Code가 실제로 읽는 **팀 공유 MCP 서버 정의**. 기본은 빈 목록(`{"mcpServers": {}}`).
- `.claude/mcp/servers/<이름>.json` — 서버 하나당 정의 조각(예시·백업). `.mcp.json`에 병합하기 전 보관·검토용.
- `.claude/settings.json` — 승인 정책:
  - `enableAllProjectMcpServers`: `true`면 `.mcp.json`의 모든 서버를 자동 승인. 기본은 `false`(서버별 승인).
  - `enabledMcpjsonServers` / `disabledMcpjsonServers`: 개별 서버 허용/거부 목록.

## 서버 추가 절차

1. `servers/<이름>.json`에 서버 정의 조각을 작성한다(아래 형식 참고).
2. 검토 후 그 내용을 루트 `.mcp.json`의 `mcpServers` 객체에 병합한다.
3. 자동 승인이 필요하면 `.claude/settings.json`의 `enabledMcpjsonServers`에 서버 이름을 추가한다.
4. Claude Code를 재시작하거나 세션에서 MCP 서버를 다시 로드해 연결을 확인한다.

## 정의 형식

### stdio 서버 (로컬 명령 실행)

```json
{
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
  "env": {}
}
```

### 원격 서버 (HTTP/SSE)

```json
{
  "type": "http",
  "url": "https://example.com/mcp",
  "headers": {}
}
```

루트 `.mcp.json`에서는 위 정의를 서버 이름 아래에 둡니다:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
    }
  }
}
```

## 주의

- 토큰·API 키 등 비밀값은 `.mcp.json`이나 이 폴더에 직접 적지 말고 환경 변수(`env`)로 참조한다.
- `.mcp.json`은 팀 공유 파일이므로 개인 전용 서버는 사용자 범위 설정에 둔다.
