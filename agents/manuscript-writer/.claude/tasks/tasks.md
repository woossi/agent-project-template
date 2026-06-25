# 작업

## 상태
진행 중

## 목표
SSCR Q1·방법론 기여 중심 논문 파트별 재작성에 앞서, 현 한국어 원고 전 섹션을 정독하고 섹션 골격·정합성 검수 결과를 정리한다(본격 재작성은 SSCR 체크리스트 확정에 막힘).

## 배경
orchestrator가 manuscript-writer에 원고 집필 4건을 배정. 그중 Task 2(파트별 재작성)는 paper-scout의 SSCR 투고 체크리스트 재생성 확정에 의존(현재 pending)하여 본격 착수가 막힘. 확정 전 선행 가능한 범위는 "현 원고 정독·섹션 골격 설계·정합성 검수"로 지시됨. 방향(확정): 방법론 기여 중심 — (1) 행정 사전 대 플랫폼 관측의 EB 수축 비교를 통한 측정-기제 이행 조작화, (2) 정보 차단형 멀티에이전트 역행추론 설계가 핵심 기여, 디지털 역량은 적용 사례.

## 입력
- /Users/ujunbin/research/UMC/umc_paper.tex (마스터)
- /Users/ujunbin/research/UMC/parts/{body_front_intro,body_ch2,body_model,body_results,body_ch4}.tex (5개 본문)
- /Users/ujunbin/research/UMC/parts/{figure_index,table_index,citekey_map,_newrefs_map}.md
- /Users/ujunbin/research/UMC/refs.bib, figures/
- .team/inbox 수신 메시지 2건(ack 완료), .team/tasks/ 배정 작업 JSON

## 기대 산출물
- 섹션별 골격·기여 매핑·정합성 검수 노트(.context/handoff/)
- (막힘 해제 후) 섹션별 재작성 계획과 실제 재작성

## 사용할 스킬
- team-inbox: peer 메시지 수신/ack
- set-team-goal(team_goal.py): 작업 상태 갱신(task-status), --store는 서브커맨드 앞 또는 root에서

## 사용할 서브에이전트
- (현재 없음)

## 필요한 결정
- SSCR 체크리스트 확정 시점·내용(paper-scout 의존) — 미확정
- 결과 4.x 절 번호 표기 정합: 서론은 4.1~4.3로 RQ 대응 안내, 본문 결과 장은 \ref 라벨 사용 — 인쇄 번호 일치 확인 필요(검수 항목)

## 위험
- 체크리스트 미확정 상태에서 재작성을 선행하면 양식 재작업 위험 → 골격·검수까지만 선행
- 근거 없는 내용 생성 금지, 검증 안 된 주장은 불확실 표시(계약 제약)

## 검증
- xelatex 컴파일 통과(그림·표·참조 해소) — 막힘 해제 후
- 전 섹션 초고 완결성·기여 명확성 점검 통과

## 완료 기준
- 5개 섹션 골격·기여 매핑·정합성 검수 노트가 .context/handoff/에 기록되고 위험·결정이 orchestrator에 회신됨
- (Task 2 본체) SSCR 체크리스트 확정 후 섹션별 재작성 완료

<!-- component-contract:start -->
## 계약 연계

- 작업은 에이전트가 실행하는 가장 작은 작업 단위이며, 에이전트가 자동으로 기록하고 갱신한다.
- 작업 패킷은 현재 상태(목표, 입력, 검증, 완료 기준)만 담고, 진행 로그와 handoff는 `.context/`에 둔다.
- `사용할 스킬`에는 필요한 능력과 절차를 참조로 적는다. 절차를 복사하지 않는다.
- `사용할 서브에이전트`에는 역할, 담당 범위, handoff 위치를 적는다.
- 결과는 작업의 검증과 완료 기준으로 되돌아온다.
<!-- component-contract:end -->
