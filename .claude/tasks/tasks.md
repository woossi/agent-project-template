# 작업

agent-template 프로젝트의 현재 작업 패킷입니다. 가장 작은 작업 단위이며, 에이전트가 자동으로 기록·갱신합니다(사용자가 큐레이션하지 않음). 작업 패킷은 현재 상태만 담고, 진행 로그와 handoff는 `.context/`에 둡니다.
작성과 갱신은 `.claude/skills/write-task/SKILL.md`를 따릅니다.
템플릿은 `.claude/skills/write-task/templates/task.md`에 있습니다.

## 현재 작업

상태: 완료

목표: Tasks→Skills→Agents 승격을 시스템이 강제하도록 구현한다(실행 작업 자동 로깅 + 조건 평가 + 승격 후보 강제 노출). 스킬/에이전트 생성 조건을 `promotion.json`으로 외부화한다.

기대 산출물:

- `.claude/hooks/task_ledger.py`(자동 로깅·`record-task`), `.claude/hooks/detect_promotions.py`(평가·노출·`resolve`)
- `.claude/policies/promotion.json`(구체 조건), 두 훅의 회귀 테스트
- 계약 선언(AGENTS.md *Enforced Promotion Loop*, CLAUDE.md, README, policies/README) 및 클론 생성기 전파

완료 기준:

- hook 테스트 30개·clone 테스트 7개 통과, end-to-end 스모크(후보 노출 → `resolve` 종료) 확인
- `update_skill_index --check`·`update_agent_index --check`·`sync_component_contracts` current
- 원장 산출물은 git-ignored `.context/`에만 기록
