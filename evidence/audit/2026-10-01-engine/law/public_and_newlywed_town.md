# Audit: 국민주택/공공분양 일반공급 & 신혼희망타운 eligibility (docs/index.html)

Sources: evidence/law/rule.xml (주택공급에 관한 규칙, 시행 2026.6.15) 제27조·제10조④⑤·제11조·제53조·부칙 제7조;
notices 2026000409/414/416 (LH 공공분양), 2026000437/438 (고덕 공공분양 84㎡), 2026820008/009/010/011 (신혼희망타운).
Current data: docs/listings.json (town pub_limits = {cap:[130,140], total_asset:36200, relax:[39700,43100]}; 성남복정2 2026820008 regulated=True, need_head=True).

Severity counts: CRITICAL 1 · HIGH 4 · MEDIUM 6 · LOW 6

---

## CRITICAL

### C1. 예비신혼부부: 예비배우자 주택·소득을 판정에서 뺌 → 무주택 '충족', 소득 '충족'이 거짓일 수 있음
- Area: 신혼희망타운 예비신혼부부 (also 공공 신혼부부 특공 예비신혼부부 via spJudge)
- Code:
  - eligibility L1039-1040: `if (p.married && p.spouseOwn) own.push('배우자 명의 주택'); ... if (!p.married) homeNote = ... '혼인신고 전: 배우자 주택 미합산';`
  - Onboarding L3054: note `'혼인신고 전이면 배우자 주택과 소득은 판정에 들어가지 않아요'`; spouse step `show:p => p.married` (L3055) so 예비배우자 주택·소득 are never asked.
  - spIncome L1806: `year = est ? (p.income||0) + (p.married ? (p.spouseIncome||0) : 0) : ...` ; dual L1807 requires `p.married`.
  - hhCount L1820: `sp = p.married ? 1 : 0` (예비배우자 not counted).
  - townItems L951: townType 'pre' → `s:'ok'` '예비신혼부부'.
- Official: 2026820008 예비신혼부부 신청자격 ① "혼인을 준비 중인 예비신혼부부로서 … 혼인으로 구성할 세대원 전원이 무주택인 자", ③ "무주택세대구성원 전원의 월평균소득이 … 130%(단, 본인 및 배우자가 모두 소득이 있는 경우 200%)", 가구원수 기준 "예비신혼부부: ‘혼인으로 구성될 세대’에 해당하는 자 전원" (L1560), 맞벌이 "본인 및 (예비)배우자가 모두 … 근로소득이 있는 경우". Same in 2026820009/010/011 and 2026000409 신혼부부 특공 ③ (L1913).
- Why wrong: the household to verify for 예비신혼부부 includes the 예비배우자 (and anyone who will be on the combined 등본). The app ignores their home, income, and headcount.
- Failure: 예비신혼부부, 본인 무주택·소득 5,000만, 예비배우자 명의 아파트 1채. App: 무주택 세대 '충족', 신청 유형 '예비신혼부부' ok, 소득 ok → "신청 가능". Actual: 신청자격 ① 위반 → 부적격 당첨, 계약 불가, 최대 1년 청약 제한.
- Fix: when townType==='pre' (or 공공 신혼부부 특공 with 예비신혼부부), ask 예비배우자 주택 보유·소득·통장 and treat them like a spouse in eligibility('무주택 세대'), spIncome (sum + dual) and hhCount (+1). Until asked, '무주택 세대' and '소득' must be 'warn', never 'ok'. Remove/qualify the L3054 note for 예비신혼부부.

## HIGH

### H1. 신혼희망타운 소득 상한을 우선·일반공급 기준(맞벌이 140%)으로 잡아, 신청자격(맞벌이 200%)인 사람을 '기준 초과'로 탈락시킴
- Area: 신혼희망타운 소득 (parsing + judgment + judge cases)
- Code: app/notice_pdf.py L478 `_parse_town_limits` reads only the table row "우선·일반공급 … 130% … 140% (본인 및 배우자가 모두 소득이 있는 경우)" → `cap:[130,140]`. index.html L966-970: `cap = pl.cap[inc.dual ? 1 : 0]` … `else if (m > spAmt(n, cap + relaxRange(p)[1])) → s:'fail', '기준 초과'`. Comment L909 states '우선·일반공급 130% (맞벌이 140%)' as the eligibility limit. tools/make_judge_cases.py L297-302 enshrines `(141, True) → "fail"`.
- Official: 2026820008 신혼부부 ③ "130%(단, 본인 및 배우자가 모두 소득이 있는 경우에는 200%) 이하인 분" (L1746), 예비신혼부부 ③ same 200% (L1757); 3단계 추첨 "공급유형별 신청자격을 갖춘 자 … 추첨" and the income table row "추첨 … 130% … 200% (본인 및 배우자가 모두 소득이 있는 경우)". Identical in 2026820009 L1014/1034, 2026820010 L1191/1201, 2026820011 L824/834. 130/140 applies only to 1단계 우선공급·2단계 일반공급.
- Failure: 맞벌이 신혼부부 3인, 월평균소득 1,200만원 (≈159%). App: '소득 (신혼희망타운) 기준 초과' → fail → 신청 불가. Actual: 신청 가능 (3단계 추첨 대상). With +20%p 출산 완화 the app's ceiling is 160% instead of 220%.
- Fix: parse two limits — eligibility `cap:[130,200]` (from 신청자격 ③ / 추첨 row) and `priority:[130,140]` (우선·일반공급 row); judge like pubGeneralItems ('충족 · 3단계 추첨만' when 140 < m ≤ 200 for 맞벌이). 한부모 stays 130 (no 맞벌이). Fix judge case town-03 and add golden data; add crosscheck for both rows.

### H2. 신혼희망타운(규제지역)에 세대주 요건을 추정 적용 → 세대원은 '신청 불가'
- Area: 신혼희망타운 / needHead / regulatedItems
- Code: app/pipeline.py L153 `need_head=bool(regulated)` default; notice_pdf.py L112 regex (`거주하는…(무주택세대의세대주|무주택세대주|무주택세대구성원)`) does not match the town notice wording, so 2026820008 keeps need_head=True (run-log L481-484 "세대주 요건을 공고문에서 확인하지 못해 규제지역 기준으로 추정"). index.html L1071-1079 pushes `{k:'세대주', s:'fail'}` (not r1) for anyone not 'head'.
- Official: 2026820008 <표1> 신혼부부/한부모 "무주택세대구성원", 예비신혼부부 "혼인으로 구성될 세대"; 신청자격 ①~④ (L1742-1771) contain no 세대주 requirement. 신혼희망타운 has no 1순위/2순위; 제27조①1다 (세대주) applies to 국민주택 일반공급 1순위 only.
- Failure: 예비신혼부부 or 신혼부부 living as 세대원 in parents' 등본 views 성남복정2 A1 → '세대주 미충족' → "모집공고일 기준 세대주가 아니에요" → 신청 불가. Actual: eligible.
- Fix: for isNewlywedTown(L) force needHead=false and skip regulatedItems. In general, when need_head is an estimate (not from notice) for 국민 general supply, render the 세대주 item as r1 (2순위 가능) and 'warn', not a hard fail (규칙 제27조①1다 is a 1순위 condition only).

### H3. 세대 소득을 비워 두면 본인+배우자 소득만으로 '충족' 판정 (같은 등본 성인 세대원 소득 누락)
- Area: 공공 일반공급 60㎡ 이하 소득, 신혼희망타운 소득 (and spJudge)
- Code: spIncome L1805-1806 `est = hhIncomeYear empty; year = est ? income + spouseIncome : ...`; pubGeneralItems L1006 `if (m <= spAmt(n, cap)) out.push({ s:'ok', v:'충족' ...})` (est only appended as text); townItems L969 same. Meanwhile hhCount (L1813-1822) adds parents/adult children to n, raising the threshold.
- Official: 2026000409 L1389/283-291 "가구원 중 주택공급신청자 및 19세 이상 무주택세대구성원 전원의 소득을 합산 … 주택공급신청자의 배우자 및 직계존비속을 포함"; 2026820008 "만 19세 이상 무주택세대구성원 전원의 합산 소득".
- Failure: 부부(합산 6,000만) + 같은 등본 부모 2명(부모 소득 4,000만) → n=4, app monthly 500만 vs 4인 100% 880만 → '충족'. Actual 833만 ≤ 880만? Change to 부모 소득 6,000만: actual 1,000만 > 880만 → 부적격; app still '충족'.
- Fix: if hhIncomeYear empty AND (eldersOnDeed>0 or adult kids on deed or unknown), return 'warn' ("세대원 전원 소득 입력 필요"), never 'ok'. Only allow the estimate to produce 'ok' when the household is known to be just 본인+배우자+미성년.

### H4. 국민주택 regulated: 세대주 요건 추정치(need_head 기본값)가 1순위 요건이 아닌 '신청 불가'로 처리됨
- Area: 국민주택 일반공급 규제지역 1순위
- Code: eligibility L1071-1079 (needHead item has no r1); regulatedItems L673 only adds the r1 세대주 item when `!L.needHead`. pipeline L153 sets need_head=True for every regulated listing when the notice sentence is not matched.
- Official: 규칙 제27조①1다 "투기과열지구 또는 청약과열지역: … 2) 세대주일 것" is a 제1순위 condition; ②: "제2순위: 제1순위에 해당하지 아니하는 자". LH 공공분양 일반공급 신청자격 = "무주택세대구성원" (2026000409 L2105, 2026000437 일반공급 ①).
- Failure: 규제지역 공공분양 (e.g., 서울/과천 LH) whose notice sentence is not parsed; 세대원 user → '세대주 미충족' → 신청 불가 instead of '1순위 불가 · 2순위 가능'.
- Fix: for houseDtl==='국민' general supply, never use needHead as a hard requirement; rely on regulatedItems' r1 세대주 item.

## MEDIUM

### M1. 신혼희망타운 통장 요건이 '1순위' 요건으로 표시돼 미달 시 "2순위로는 신청할 수 있어요"
- Code: accountItems L655 `{ k:'청약통장 가입기간', r1:true, ... }` for all 국민 including town; acctNeedMonths L619-622 fallback `regulated ? 24 : capital ? 12 : 6` ignores town (publicItems L637 uses 6 for town but accountItems does not). eligibility L1095 `rank2 = fails.every(i => i.r1)`; regulatedItems also adds r1 items ('세대 5년 내 당첨 없음 (규제지역 1순위)', '2주택') for regulated towns.
- Official: 2026820008 ② "입주자저축에 가입하여 6개월이 경과되고 … 6회 이상 납입한 분" is a 신청자격 (no 순위 in 신혼희망타운). 
- Failure: (a) town, 가입 4개월, 납입횟수 미입력 → 가입기간 fail(r1) → "2순위로는 신청할 수 있어요" (false 신청 가능). (b) town notice where account_months is not parsed in 수도권 → requires 12개월 → 8개월 가입자 falsely fails. (c) 성남복정2: someone whose 세대 won a 비규제 민영 4 years ago (no 재당첨제한) → '세대 5년 내 당첨 (규제지역 1순위)' fail → told "1순위 불가·2순위 가능" though town has no such rule.
- Fix: acctNeedMonths returns [6,…] for town; for town set r1:false on account items and skip regulatedItems.

### M2. 공공 일반공급 출산가구 자동차 완화 +20%p 한도 1만원 차이 (5,450 vs 공고 5,451만원)
- Code: pubGeneralItems L1012 `lim = (v,k) => Math.round(v*(1+k/100))` → lim(4542,20)=5450; spJudge L1946 hardcodes 5451 (inconsistent).
- Official: 2026000409 <표3> "자동차 49,960천원 이하 / 54,510천원 이하".
- Failure: 자녀 2명(23.3.28 이후 1명 포함), 차량가액 5,451만원 → app '기준 초과' fail; 공고상 충족.
- Fix: use parsed <표3> values (add to parse_pub_limits: real_estate_relax, car_relax) instead of computing.

### M3. 자동차 가액 하나만 받아 공공 일반공급(최고가 1대)과 신혼희망타운(전 차량 합계)을 같은 값으로 판정
- Code: L3102 `{ k:'carValue', l:'자동차 가액' }`; pubGeneralItems L1012 uses p.carValue; townAssetParts L920 `car: v('carValue')`.
- Official: 2026000409 <표2> "해당 세대가 2대 이상의 자동차를 소유한 경우는 각각의 자동차가액 중 높은 차량가액을 기준"; 2026820008 <표3> ④ "해당세대가 보유한 모든 자동차의 가액을 합하여 산출".
- Failure: 차 2대(3,000·2,500만). If user enters 5,500 (합계) → 공공 일반공급 '자동차 기준 초과' (false fail; correct 3,000 ≤ 4,542). If enters 3,000 → town 총자산 understated by 2,500만 → possible false 총자산 '충족'.
- Fix: ask '가장 비싼 차' and '모든 차 합계' separately (or number of cars + each value).

### M4. 혼인 7년 초과·자녀 생년월일 미입력이면 '6세 이하 자녀 없음'으로 탈락
- Code: townItems L942 `kid6 = p.pregnant === true || (p.youngestBirth && youngestBirth > ref-7y)`; L947-948 `else if (p.kidsMinor == null && p.pregnant == null) warn; else fail '혼인 7년 초과 · 6세 이하 자녀 없음'`; same for 한부모 L953-954.
- Official: 2026820008 ① "6세 이하의 자녀(만 7세 미만으로, 태아 포함)를 둔 …".
- Failure: 혼인 9년, kidsMinor=2, youngestBirth blank, pregnant=false → fail, though the youngest may be 4.
- Fix: if kidsMinor>0 and youngestBirth empty → 'warn' (자녀 생년월일 입력 필요).

### M5. 청약저축 보유자를 공공분양에서 '불가'로 판정
- Code: publicItems L638-640: acctType 'saving' (청약저축) → `s:'fail'` 'LH 공공분양은 주택청약종합저축으로 신청해요'.
- Official: 규칙 부칙 제7조 "2015년 9월 1일 전에 가입한 청약저축, 청약예금 및 청약부금에 대해서는 … 종전의 「주택공급에 관한 규칙」에 따른다" (청약저축 = 국민주택 청약 통장). Notices say conversion is needed only "전환하여 해당 주택에 신청하고자 할 경우" (2026000414 L131) and <표8> "저축총액(주택청약종합저축 및 청약저축은 매월 최대 25만원까지만 인정)" (2026000414 L2604) — 청약저축 is used directly.
- Failure: 2010년 가입 청약저축(납입 180회) 보유자 → '통장 종류 (공공분양) fail' → 신청 불가. Actual: 국민주택 1순위 신청 가능.
- Fix: treat 'saving' as valid for 국민주택 (no conversion needed); keep 예금·부금 → 전환 필요 note.

### M6. 소득 기준을 '작년 세전 연소득'으로 받음 — LH는 조회 시점 건강보험 보수월액 등 현재 소득으로 판정
- Code: L3099/L3100 labels '본인 세전 연소득 (작년)', '세대원 전원의 작년 세전 소득 합계'; spIncome monthly = year/12.
- Official: 2026000409 L1200-1211 "사회보장정보시스템을 통해 <표6> … 공고일 이후 변동된 소득금액이 조회된 경우 해당 금액을 당사자의 소득금액으로 간주", 소득자료 반영순위 ① 국민건강보험공단(보수월액). Same in 2026820008 L1540-1542.
- Failure: 작년 연봉 9,000만, 올해 1억2,000만으로 인상 (3인, 외벌이 100%=753만) → app 750만 '충족'; LH 조회 보수월액 1,000만 → 부적격.
- Fix: ask current monthly salary (건강보험 보수월액) or add a warning when this year's pay differs; label the estimate.

## LOW

### L1. 국민 1순위 경쟁 순차: 40㎡ 이하는 '납입횟수' 순인데 항상 '저축총액' 순으로 안내
- Code: publicItems L645 note '3년 이상 무주택세대구성원 중 저축총액 … 많은 순'.
- Official: 규칙 제27조② 2호 "40제곱미터 이하인 주택의 공급순차 가. 3년 이상의 기간 무주택세대구성원으로서 납입횟수가 많은 자 나. 납입횟수가 많은 자".
- Fix: branch on L.area ≤ 40. (No ≤40㎡ listing in current data.)

### L2. 공공 일반공급 2단계 우선공급은 1순위자만 — 2순위인데 소득 ≤100%면 '충족'(우선공급 가능처럼) 표시
- Code: pubGeneralItems L1006 `v: pri != null && m > spAmt(n, pri) ? '충족 · 추첨공급만' : '충족'` — ignores 순위.
- Official: 2026000409 L2181-2183 "2단계 우선공급(1순위자) … <표7>에 따른 1순위자로서 … 100%(…140%) 이하인 자".
- Fix: also mark '추첨공급만' when 납입/가입 1순위 미달.

### L3. 공공 일반공급 1단계 신생아 우선공급(50%) 미표시
- Official: 2026000409 L2118-2121 "2세 미만(2세가 되는 날을 포함) 자녀 … 100%(…140%) 이하 … 공급량의 50%"; 2026000437 (60㎡ 초과도) "2세 미만 … 자녀(태아를 포함) … 50%".
- Effect: information only (no false eligibility).

### L4. 맞벌이 판정은 '둘 다 소득 > 0'으로만 봄
- Code: spIncome L1807 `dual: married && spouseIncome > 0 && income > 0`.
- Official: "본인 및 배우자가 모두 「소득세법」 제19조제1항 사업소득 또는 제20조제1항 근로소득이 있는 경우" (2026000409 L171, 2026820008).
- Failure: 배우자 소득이 연금·임대·이자소득뿐 → app 맞벌이 200% 적용 → false '충족' for 100–200% band. Fix: ask income type or label.

### L5. 신혼희망타운 부채의 임대보증금 상한 미반영
- Official: <표3> ⑤ "임대보증금(단, 해당 부동산가액 이하의 금액만 반영)"; app subtracts p.townDebt as entered. Fix: cap the 임대보증금 portion at the property value or note it.

### L6. 출산가구 완화: 쌍둥이 태아(fetusCount 2)는 2명 이상(+20%p)인데 birthRelax 가 fetusCount를 보지 않음
- Code: birthRelax L1846-1849 uses kidsMinor/youngestBirth/pregnant only. If kidsMinor excludes the twins → +10%p (conservative 'warn', not false ok). Minor.

---

## Verified correct
- 제27조①1가/나/다: acctNeedMonths & publicItems fallback 수도권 12·비수도권 6·규제 24 (L621, L637) matches law; parsed account_months/deposit_count (12 for 409/414/416/437/438, 6 for towns) match notices.
- regulatedItems for 국민 includes 세대주(r1) and 세대 5년 내 당첨 (제27조①1다 2)·3)) when need_head parsed false.
- monthsBetween/가입기간 '1년이 지난' on the anniversary date counts as satisfied (consistent with 민법 기간 계산).
- 공공 일반공급 소득 cap [100,200], priority [100,140], 부동산 21,550만, 자동차 4,542만 parsed correctly for 2026000409/414/416; area_max 60 for 414/416; >60㎡ (437/438, 414 74–84㎡) have no 소득·자산 (notice "(전용면적 60㎡ 이하의 경우)").
- SP_INCOME_2025 values and spAmt rounding match <표4> (100/130/140/200/210/220% rows) and 8인 초과 579,278원.
- 공공 자산 출산 완화 부동산 23,705/25,860만, 자동차 +10%p 4,996만 match <표3>.
- 출산가구 완화 기준일 2023-03-28 inclusive, 1명 +10%p / 2명 이상(이전 출생 자녀 포함) +20%p (birthRelax/relaxRange) match notices.
- 가구원수: 공공 일반공급·신혼희망타운 = 무주택세대구성원 전원 + 태아 수 (hhCount all=true for 국민 non-first) matches 2026000409 가구원수 표 and 2026820008.
- 신혼희망타운 혼인 7년: `marriedOn >= ref-7y` matches "2019.08.10.~2026.08.10.에 속한 자" (inclusive); 6세 이하 = 만 7세 미만 `youngestBirth > ref-7y` matches.
- 한부모: 130% only (no 맞벌이), 6세 이하 자녀(태아 포함) — matches notices (except 한부모가족지원법 증명 not checked, acceptable).
- 총자산 구성 (부동산+금융(예금·주식·보험 해약환급금 등)+기타(임차보증금 등)+자동차−부채), 기준 36,200만, 완화 39,700/43,100만 match <표3>/<표4>; boundary `≤`.
- 수익공유형 모기지: shown as a post-selection obligation (L2616: '신청 자격과는 별개', 30% 이상 의무, 정산 10~50%) — matches notice L203-256, L1229-1231; not used in eligibility.
- 60세 이상 직계존속 주택 예외 (제53조6호) applied to 국민 general supply (not excluded) — correct.

## Unverifiable here
- 공공주택 특별법 시행규칙 별표6 / 별표6의3 text (not fetched; findings rely on notices, which cite them).
- Whether LH accepts 청약저축 without conversion for every 2026 공공분양 notice (M5 rests on 규칙 부칙 제7조 + notice wording; confirm with one LH notice's 청약통장 FAQ).
- Whether hhCount's kidsMinor includes fetuses (affects L6 only).
