# runs index (derived view — do not hand-edit)

Regenerated from `.project/runs/*.json` by `canon_integrity.py fold`. The immutable JSON records are the canon. Back-references (cited_by) are computed, not stored.

## RUN001 [active]
HLM 무조건(영)모형 ICC 산출
- script=HLM 무조건/null 모형 적합 — 자치구간 분산 / (자치구간 분산 + 개인내 분산)으로 ICC 산출
- inputs=['D001']
- cited_by=[]

## RUN002 [active]
HLM 2023-2024 통제(조건부)모형 적합
- script=서울서베이 2023-2024 통합 자료에 개인수준 통제·상호작용을 투입한 HLM 모형1~모형4 적합
- inputs=['D001']
- cited_by=[]

## RUN003 [active]
LLM 분류 파이프라인(단계0-4) 및 인간 대조 검증
- script=텍스트 코퍼스에 키워드 필터·행정동 매칭·LLM 6차원 분류를 적용하고, LLM-인간 이중 코딩 일치도(정밀도·Cohen κ)와 차원별 F1을 산출
- inputs=['D002']
- cited_by=[]

## RUN004 [active]
정보차단 멀티에이전트 역행추론 단계 E(223건)
- script=강북·노원·중랑 3구의 정보차단 멀티에이전트 역행추론에서 judgment-synthesizer(opus 계열)가 단계 E 판정과 지역 가설을 생성
- inputs=['D002', 'D003']
- cited_by=[]

## RUN005 [active]
UMC 종합지수 산출 및 차원내 표준화(z_shift)
- script=EB 수축 후 서울내 min-max 정규화로 UMC 종합지수를 산출하고 차원내 표준화로 z_shift를 계산
- inputs=['D003']
- cited_by=[]

