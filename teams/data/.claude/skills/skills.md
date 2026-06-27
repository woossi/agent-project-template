# 팀 스킬 인덱스 — data 팀

워커 다수 간 협력(워커 간 워크플로우)을 고정한 팀 스킬. 오케스트레이터가 스킬 하나로 산출물을 얻게 하는 것이 목적.
승격: detect_team_promotions.py가 같은 팀 워커 ≥2의 작업 전달 반복을 후보로 띄움.

- **data-artifact-pipeline** — 원천 압축 → 추론 재실행 → registry 등록 → cross-team(write·review) 전달 사슬을 단계 소유권·핸드오프 시점·필수 메타(모델버전·시드·프롬프트·sha256)와 함께 고정. data-engineer·data-curator·inference-runner·data-lead 협력 워크플로우.
