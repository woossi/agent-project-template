# 팀 메모리 — data 팀

팀 합의·맥락(워커 간 공유, 회사 전체는 아님). 회사 결정은 .project/memory/, 워커 개인은 teams/data/<워커>/.claude/memory/.

> 기록 권한: 이 팀 메모리는 **팀장(data-lead)/orchestrator만** 기록한다(공유 메모리 owner 게이트). 워커는 자기 폴더 private memory에만 쓴다.

## 팀 결정
- **패킷 dfc9ae89 종결 합의**(2026-06-27): R1(프롬프트 전문·코드·해시·커밋 fff4127·외부저장소 의존 제거)·R2(danggeun 가드레일 3축) 충족 확인. 전달 경로 승인 — R2+R1부록→write, R1추출분→data-curator. §7.1 진단 정합.
- **DATA_ETHICS §4 미확인 분리**: ToS조항·IRB·robots 미확인은 write 확정 서술 금지 조건 유지. data-lead가 미확인 추적 등록.
- **음성대조구 = 강서구**(inference-runner 실측): 영등포(CQ z_shift +1.432)·관악(+1.835) 둘 다 부적격(|z|≫0.5). 재분류 파이프라인 기준.
- **phase00 보류 게이트**(2026-06-27): phase00 모델 실측은 data-curator 소관, review 게이팅 조율. write에 전파·실측 회신 대기.
- **v7→v8 스키마 전환**: 03_umc_classified.csv(131,793행)는 v8 스키마(condition_cue·pathway_cue·absence_cue 등) 사전 라벨링 대상. v8 예약 슬롯 등재.
