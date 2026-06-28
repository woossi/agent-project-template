# risk index (derived view - do not hand-edit)

Regenerated from `.project/risks/*.json` by `canon-enforce fold`. The immutable JSON records are the canon. Back-references (cited_by) are computed, not stored.

## R001 [mitigated]
심사자 위험: ICC 0.49%가 작아 '지역 효과 없음·지역맥락 무의미'로 과소해석될 위험
- related_claims=["C001"]
- severity=medium mitigation=ellen2016(작은 평균격차가 분리 부재를 뜻하지 않는다)을 근거로, 작은 자치구간 분산 비중이 지역 차원 무의미를 함의하지 않음을 본문에서 명시한다. ICC는 무조건 모형의 분산 분해 결과로 보고하고, 개인 수준 변량이 더 크게 나타났다는 관측 진술로 한정한다.
- cited_by=[]

## R002 [mitigated]
오분류 위험: LLM 분류 결과를 '사실'로 과잉해석할 위험
- related_claims=["C002","C004","C008"]
- severity=medium mitigation=인간 코더 대비 IRR로 분류 신뢰도를 검증한다 — 관련성 정밀도 84.7%, 주 차원 κ=0.673(C004). LLM 분류 산출(C002의 지역 단위 디지털 신호, C008의 z_shift)은 '확인되었다·나타났다' 관측 진술로 한정하고, 차원내 표준화 z_shift는 우선검토 후보를 가리키는 신호로 표기해 확정 사실로 읽히지 않게 한다.
- cited_by=[]

## R003 [mitigated]
과잉해석 위험: 단면자료에서 인과('영향을 미쳤다')로 과장될 위험
- related_claims=["C003","C006"]
- severity=medium mitigation=서울서베이 통합 표본은 단면 설계이므로 인과 주장을 배제한다. clarity R9 규약에 따라 '영향을 미쳤다' 대신 '관련된다·차이를 보였다·낮게 나타났다'로 표기를 완화한다 — 저학력 집단의 20점 이상 격차(C003), 65세 이상 집단의 약 9점 격차(C006)는 집단 간 관측 차이로만 진술한다.
- cited_by=[]

## R004 [active]
심사자 위험: 이론적 근거 없이 실증 지표·가설을 제시한다는 grounds 부재 위험
- related_claims=["C007","C009"]
- severity=medium mitigation=UMC 종합 지수의 척도 구성 근거(C007)와 역행추론 가설 도출 절차(C009)를 이론·방법 절에서 명시하고, 지수·가설을 확정 결과가 아니라 탐색적 산출(우선검토 후보·지역 가설)로 제시한다. 이론 연결이 본문에서 보강되면 mitigated로 전환한다.
- cited_by=[]
