# 청약 자격 블라인드 감사 — 지시서

당신은 한국 아파트 청약 자격을 **원문만 보고** 판정하는 독립 검토자입니다. 어떤 앱의 판정을 검증하는 데 쓰입니다.
앱의 코드·결과는 보지 않습니다. 아래 금지 목록을 지키세요.

## 읽을 수 있는 것 (이것만)
- 사례 파일: (아래에서 지정한 cases_*.json)
- 모집공고문 원문 텍스트: /home/claude/cheongyak.github.io/evidence/notices/<notice_id>.txt  (PDF 를 텍스트로 뽑은 것. 표가 깨져 있을 수 있음)
- 법령 원문: /home/claude/cheongyak.github.io/evidence/law/rule.xml (주택공급에 관한 규칙 전문, 2026.6.15 시행),
  /home/claude/cheongyak.github.io/evidence/law/byeolpyo_1.txt (별표 1 가점제 적용기준), byeolpyo_2.txt (별표 2 예치기준금액)

## 금지 (열지 마세요)
docs/ 폴더 전체(특히 docs/index.html, docs/listings.json), tools/, tests/, app/, WORK.md, HANDOFF.md, FEATURES.md, 그 밖의 저장소 파일, 웹 검색.

## 프로필 필드 뜻 (금액 단위: 만원, 날짜 YYYY-MM-DD)
- homeSido/homeSigun: 지금 주민등록 주소 시·도/시·군·구. sidoOwnSince=areaSince: 그 시·도(시·군)에 계속 산 시작일
- household: head=세대주, parents=부모님 세대의 세대원, spouse=배우자 세대의 세대원. headSince: 세대주가 된 날
- selfOwn: 본인 주택 소유. spouseOwn: 배우자 주택 소유. hhHomes: 세대 전체 주택 수('0','1','2+', 분양권 포함)
- married/marriedOn: 혼인 여부/혼인신고일. birth: 본인 생년월일
- acctType: 청약통장 종류 all=주택청약종합저축, deposit=청약예금, ''=통장 없음. acctSince 가입일, acctAmount 예치금(민영 기준 금액),
  acctCount 납입 인정 횟수, acctPaid 납입 인정 금액(공공 기준)
- win5y: 세대원 누구라도 과거 5년 내 당첨. recentWin: 재당첨 제한 기간 중
- dependents: 부양가족 수(가점용, 본인 제외). kidsMinor: 만 19세 미만 자녀 수(태아 포함). youngestBirth: 가장 어린 자녀 생일. pregnant: 임신 중
- hhSize: 가구원수. kidsOnDeed: 같은 등본 자녀 수. eldersOnDeed: 같은 등본 직계존속 수
- income/spouseIncome: 본인/배우자 작년 세전 연소득. hhIncomeYear: 세대 연소득 합. realEstate: 부동산 자산. carValue: 자동차가액
- hhNeverOwned: 세대원 모두 주택을 가진 적 없음. taxYears5: 소득세 5년 이상 납부. elder65: 만 65세 이상 직계존속 3년 이상 부양
- 입력이 없는 값(null, '')은 '모름'입니다. 모르는 값 때문에 결론이 갈리면 그 항목은 '확인 필요'입니다.

## 할 일 (사례마다)
공고문(notice_id) 중 이 주택형(house_type, 전용 area_m2)의 **일반공급**에 대해, 입주자모집공고일(notice_date) 기준으로 판정하세요.
1. general: 다음 중 하나
   - "ok": 1순위로 신청 가능 (모든 요건 충족이 확인됨)
   - "rank2": 1순위 요건은 못 채우지만 2순위로는 신청 가능
   - "no": 일반공급 신청 자체가 불가 (예: 공고문의 거주지역 요건 밖, 무주택 요건 위반, 소득·자산 초과 등)
   - "unsure": 주어진 정보로는 결론을 낼 수 없음 (어떤 정보가 없어서인지 적기)
2. general_reasons: 결론을 가른 요건마다 [요건, 충족/미충족/모름, 근거(공고문 문장 일부 또는 법령 조항)] 목록
3. region_priority: 해당지역 우선 대상인지 "해당" / "기타" / "신청불가지역" / "모름" (공고문 거주 요건 기준)
4. score: 민영주택이면 가점(84점 만점) 합계를 별표 1 로 계산 (무주택기간·부양가족·통장 가입기간). 공공(국민)주택이면 null. 계산 못 하면 null
5. sp: sp_type 이 있으면 그 특별공급(newlywed 신혼부부, first 생애최초, multichild 다자녀, elder 노부모부양, newborn 신생아) 자격을
   "ok"/"no"/"unsure" 와 핵심 사유 한 줄로. 공고문의 해당 특별공급 자격 요건(소득·자산·무주택·혼인기간·자녀 등)을 따르세요
6. confidence: high/medium/low 와 애매했던 점

공고문 텍스트에서 표가 깨져 값을 확정할 수 없으면 그렇다고 적고 "unsure" 로 두세요. 추측으로 채우지 마세요.

## 출력
지정한 출력 파일에 JSON 배열로 저장: [{"id","general","general_reasons","region_priority","score","sp","confidence"}]
마지막 답변에는 사례 수와 저장 경로, 판정이 특히 애매했던 사례만 짧게 적으세요.
