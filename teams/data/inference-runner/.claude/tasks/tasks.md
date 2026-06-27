# 작업

## 상태
진행 중 (선행분 완료, W1·W4 통지 대기)

## 목표
당근 게시글 전면 재분류 파이프라인 소유 — W2(검색확장)·W3(API분류)·W6(EB재계산)·W7(역행추론 재실행).
사용자 결정(2026-06-27): 재분류 = 학위논문 분석토대 재구축의 선행 게이트. 파일럿 우선 → 4지표 → 전수 GO/NO-GO.

## 사용할 스킬
- reminders-team-bridge (백로그 진행기록)
- team-inbox (orchestrator 조정)

## 진행
- [x] orchestrator 지시 수신·ack, 명세 정독(karrot-reclassification-spec-2026-06-27.md)
- [x] **음성대조구 선정**: 강서구 권고(CQ z=-0.061·n=371). orchestrator 제안 영등포·관악은 |z|≫0.5 부적격 회신. 근거: .context/karrot-reclass/negative-control-gu-selection-2026-06-27.md
- [x] **W2 τ설계 골격**: 6차원 시드앵커·코사인 임계 precision/recall 보정 절차. .context/karrot-reclass/W2-tau-design-2026-06-27.md
- [x] **W3 API스크립트 골격**: 모델ID고정·temp0·seed·prompt_version·사이드카 run.json·review_text_300·C-M-O 필드. py_compile PASS·의존성 게이트 동작. .context/karrot-reclass/W3-api-classify-skeleton.py
- [x] 백로그 annotate(EA5132EC), orchestrator reply 발신
- [x] **W4 코드북 v8 저작 완료**(2026-06-28, 내가 소유 — W3 분류 스크립트 작성자). umc_classifier_v8_20260627.md: v7 전보존 + C-M-O 3필드·차원CODE·confidence·정보차단경계 §10·버전박제(sha256 f2cf79c5 자기일관). W3 스켈레톤 동반 갱신(--absence-typology/--guard-state 게이트·사이드카 hash). py_compile/게이트exit2/hash정합 검증완료. 백로그 통지(17F09C06)·팀장 보고(post --to-team data, msgid …97db5e21) 완료. 모델핀만 orchestrator 대기.
- [x] **A-1 게이트 상태 보고·probe 정정**: 재실행 GO 보류 유지(무단 LLM 0). 223 유실 미해소. 내 선결 완료·GO 결정 대기. 백로그 정정(C3668CDD)·팀장 보고 포함.
- [ ] **차단**: W1(daangn 압축DB, data-engineer) 완료 통지 대기
- [ ] **차단**: 임베딩 모델ID·API분류 모델핀 orchestrator 회신 대기
- [ ] **차단**: A-1 재실행 GO 사용자/orchestrator 결정 대기(223 처리 방향 포함)
- [ ] (대기해소 후) 임베딩 산출·τ확정(stats-validator 협업)·파일럿 분류 실행

## 게이트
- 무단 대량 LLM/API 실행 0 유지. 골격은 의존성 미충족 시 hard-stop(exit 2).
- 생산자/검증자 분리: κ/α IRR은 stats-validator(W5). 내 산출을 내가 검정하지 않음.
