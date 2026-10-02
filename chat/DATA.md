# 청약봇 V2 데이터 사전 (STEP 0-1, 2026-10-02)

청약봇이 쓰는 모든 값은 `{값, 상태, 출처, 기준일}` 로 다룬다. 상태가 없는 값은 답에 쓰지 않는다.
설계 문서: Claude 문서 '청약봇 V2 실행 계획 (STEP 0·1)'.

## 상태 4가지

| 상태 | 화면 | 뜻 |
| --- | --- | --- |
| `확인` | 초록 점 · 확인 · 출처 | 청약홈·모집공고문에서 읽은 값, 국토부 실거래 원자료, 판정 엔진 결과 |
| `외부` | 노랑 점 · 외부 · 출처 | 경로 API 시간, OpenStreetMap 역·학교 위치 |
| `추정` | 노랑 점 · 추정 · 근거 | 시세 추정, 직선거리 도보 시간, 같은 면적대 사례로 본 방·욕실 |
| `확인 불가` | 회색 점 · 확인 불가 | 근거 없음·읽기 실패·API 실패. 숫자를 지어내지 않는다 |

## 필드

| 필드 (listings.json) | 값 | 상태 규칙 | 출처 | 비고 |
| --- | --- | --- | --- | --- |
| name, address, sido, district | 공고명·주소·지역 | 확인 | 청약홈 | |
| kind, category, house_dtl | 공급 유형 | 확인 | 청약홈 | |
| unit, area | 주택형·전용면적 | 확인 | 청약홈 | |
| price | 분양가(최고가) | 확인 | 청약홈 공급금액 | crosscheck 로 공고문 대조 |
| households, special_units | 주택형 일반/특공 세대수 | 확인 | 청약홈 | 0 이면 genNone |
| notice, apply, apply_end, winner | 일정 | 확인 | 청약홈 | 마감 여부 = statusOf |
| competition, sp_competition | 경쟁률·당첨 가점 | 확인(있을 때) | 청약홈 결과 | 없으면 확인 불가 |
| mkt_low, mkt_base, mkt_comps | 시세 | 추정 | 국토부 실거래가 | 근거 거래 목록 있음 |
| geo | 좌표 | precision=exact → 확인, dong → 거리 계산에 쓰지 않음 | 네이버 지오코딩 | STEP 0-5 |
| nearby | 역·학교·직선거리·도보 분 | 추정(직선) | OpenStreetMap | geo.precision=dong 이면 확인 불가 |
| **complex** | {households, buildings, single, status, src, quote} | 공급규모 문장을 읽으면 확인, 못 읽으면 확인 불가 | 모집공고문 '공급규모' | STEP 0-2, 기능 complex_size |
| complex.single | no · maybe · unknown | no=동 2개 이상, maybe=동 1개 또는 (동 모름·100세대 미만), unknown=근거 없음 | 위 값에서 계산 | '나홀로 제외'면 no 만 후보 |
| rooms (예정) | {bed, bath, status, basis} | 공고문 표에서 그 타입 침실·욕실 → 확인, 같은 면적대 확인 사례 5개 이상 → 추정, 그 밖 → 확인 불가 | 모집공고문 | STEP 0-4, 추정은 하드 필터로 쓰지 않음 |
| archive (예정) | 과거 공고 요약 | 확인 + '과거 공고' 표시 | 청약홈 API | STEP 0-6 |
| commute (예정, 서버 캐시) | 자동차·대중교통 분, 기준 시각 | 외부, 실패 시 확인 불가 | 네이버 Directions 5 · 카카오맵 대중교통 | STEP 0-7 |

## 판정 (화면 엔진, 브라우저에서만)

eligibility · spJudge · townItems · eligBucket(일반 0세대는 특공 기준) · myScore · regionScore · funding · grade.
청약봇은 이 결과를 그대로 쓰고 다시 계산하지 않는다. 내 조건은 서버로 보내지 않는다.
