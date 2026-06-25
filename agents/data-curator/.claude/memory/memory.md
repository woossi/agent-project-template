# Memory — agent: data-curator

Private working memory (facts this agent learns while working).
Team-wide decisions and goals live in the team store (.team/memory, .team/goals).

## Durable Facts

- UMC 분석 프로젝트 루트: `/Users/ujunbin/project/umc`. 데이터 레지스트리는 `analysis/_data_registry.md`(2026-06-25 현행화).
- analysis 디렉토리 계보: `part 3`는 2026-05-18 통합 스냅숏이며, 최신 분석 결과는 원본 디렉토리(`02. baysian`, `03. Test-for-inference`)에 있다. `01. Text_preprocessing`은 `text-preprocessing`의 구버전 중복.
- 활성 산출물(2026-06-25 rename): 영문 보고서 `docs/umc_report_en_20260614.docx`, 국문 `docs/umc_report_ko.md`, 발표 `ppt/umc_presentation_en_20260618.pptx`. 경로 권위 registry는 `config/umc_project_paths.json`.
- ppt 보존 필수: `High-Five_20260507.pptx`(데이터소스 권위본), `HighFive_Step3_Submission.pptx`(config step3 등록).
- 정리 격리분은 삭제하지 않고 `<프로젝트>/tmp/_cleanup_<YYYYMMDD>/`로 이동하고 `MANIFEST.tsv`+README로 복원 가능하게 둔다.
- `.team/` 공유 store(goals/inbox 등)는 workspace guard가 Read 도구를 차단하므로 Bash(`cat`)로 읽는다. 작업 경계 내 외부 경로(`/Users/ujunbin/project/umc`)는 Read 가능.

## 선호 (Derive: preference)

- 큐레이션 시 구버전 '제거'는 즉시 삭제가 아니라 tmp/_cleanup_<날짜>/로 격리 후 검토하는 방식을 선호한다(되돌리기 가능).
- 산출물 파일명은 소문자 snake_case + 끝에 `_YYYYMMDD`(연도 데이터는 `_2023`/`_2024`) 규칙을 따른다. 그림 접두사 `fig_`, 보고서 `umc_report_{en,ko}`, 발표 `umc_presentation_{lang}`.

## 승격 관찰 후보 (재발 시 write-skill)

- `curate-project-assets`(가칭): 외부 프로젝트 디렉토리 인벤토리 → 최종/구버전 분류 → 안전 격리(매니페스트+복원 README) → 데이터 레지스트리 갱신. 2026-06-25 1회 실행(UMC). 다른 프로젝트 목록(project_neighborhood, project_crypto)에 재적용 시 스킬로 승격.
