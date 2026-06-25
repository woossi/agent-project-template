# 작업

team-umc 팀의 현재 작업 패킷입니다. 가장 작은 작업 단위이며, 에이전트가 자동으로 기록·갱신합니다(사용자가 큐레이션하지 않음). 작업 패킷은 현재 상태만 담고, 진행 로그와 handoff는 `.context/`에 둡니다.
작성과 갱신은 `.claude/skills/write-task/SKILL.md`를 따릅니다.

## 현재 작업

상태: 진행 중 (orchestrator — 백로그 분해·할당·추적)

목표: UMC 분석 결과를 SSCR(Social Science Computer Review, SAGE Q1) 투고 원고로 완성. 방향 '방법론 기여 중심'(EB 수축 측정-기제 이행 + 정보차단 멀티에이전트 역행추론, 디지털 역량은 적용 사례) 확정.

작업 추적 일원화: **진실원 = `.team/tasks/` JSON**(team_goal.py 관리). 이번 세션의 임시 TaskList(#1~#3)는 폐기. 9개 팀 작업 분배 완료:
- paper-scout(2): SSCI Q1 저널 선정[done] · SSCR 체크리스트 재생성[pending]
- data-curator(3): part 3-3 프롬프트 수정 · 저널 양식·포맷 정렬 · 투고 패키지 작성
- manuscript-writer(4): 전 섹션 정합성 검수 · 파트별 재작성 · 방법론 기여 Q1 정렬 검수 · 영문 번역

이번 세션 정리 내역:
- inbox store 경로 버그 수습: 잘못된 store 2곳(.claude/skills/team-inbox/.team, agents/paper-scout/.team)에 갇힌 메시지를 root .team로 재발송하고 디렉토리 제거. CLI는 root 실행 또는 `--store` 절대경로(서브커맨드 앞) 필수.
- 쓰레기 파일 CLAUDE_AGENT_NAME=paper-scout.txt 삭제.
- SSCR 체크리스트 산출물 유실 확정(전수 find 부재), 미리알림 노트 '완료' 기록 정정.
- 원고 작업을 data-curator → manuscript-writer 이관(과부하 해소).

완료 기준:
- 전 섹션 초고 완성·방법론 기여 명확화·SSCR Q1 양식/투고 요건 충족, 투고 패키지 완비
- 9개 팀 작업 done, 지도교수 리뷰 통과

미해결 위험:
- SSCR 체크리스트 재생성 전까지 manuscript-writer의 파트별 재작성 본격화 불가(의존).
- peer들이 CLI를 root 외에서 상대경로로 실행하면 store 어긋남 재발 가능 — 통지에 경고 포함함.
