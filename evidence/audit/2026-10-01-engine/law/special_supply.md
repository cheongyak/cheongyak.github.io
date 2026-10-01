# Audit: special-supply (특별공급) eligibility engine — docs/index.html

Scope: SP_INCOME_2025 / SP_PER_PERSON / SP_ASSET (L1772-1776), SP_RULES (L1780-1795), spTypesFor (L1797), spIncome (L1804), hhCount (L1814),
birthRelax/relaxRange (L1846-1855), spJudge (L1857-1955), mcScore (L1959), areaResidence (L2002), pubPoints (L2014), eligibility() (L1030).
Sources: evidence/law/rule.xml (주택공급에 관한 규칙, 2026.6.15 시행), notices 2026000103 (민영 분당, 투기과열), 2026000443 (민영 부산),
2026000453/0399/0403 (민영), 2026000409/0414/0416/0437 (LH 공공분양). No files were edited.

Severity key: CRITICAL = a false "가능" on an input the user already gave. HIGH = a false "가능" that is likely. MEDIUM = a false "불가", a wrong stage, or a false "가능" in narrower cases. LOW = scores/labels or edge cases.

---

## Findings

### SP-01 · CRITICAL · Special-supply verdict ignores 재당첨 제한 (recentWin)
- **Current code:** spJudge reads only two items from eligibility(): '무주택 세대' (L1864-1865) and '거주지' (L1870). It never reads `p.recentWin`. That flag is used only in eligibility()'s general-supply item (L1085). supplySummary (L2541-2543) shows the special-supply verdict separately.
- **Official rule:** 제54조① says that someone in the household of a winner of 분양가상한제 / 투기과열 / 청약과열 / 공공 housing "재당첨 제한기간 동안 다른 분양주택(…투기과열지구 및 청약과열지역이 아닌 지역에서 공급되는 민영주택은 제외)의 입주자로 선정될 수 없다". Every special-supply section of the LH notices repeats this, e.g. 2026000409 다자녀/노부모/생애최초/신혼/신생아 유의사항: "재당첨 제한 기간 내에 있는 분 및 그 세대에 속한 분 … 신청할 수 없습니다". The regulated 민영 notice 2026000103 (생애최초/신생아/노부모 ③) says "재당첨제한이 있는 세대에 속하지 않는 분".
- **Failure scenario:** A user answers "지금 재당첨 제한 기간인가요? → 예". The general-supply row shows 신청 불가 (재당첨 제한). The special-supply row still shows "신혼부부·신생아 가능" for an LH 공공분양 or a 투기과열 민영. If they apply and win, it is a 부적격 당첨 with a 1-year selection ban.
- **Fix:** In spJudge, when `p.recentWin === true` and (`pub` || `L.regulated` || the notice is 분양가상한제), add a fail. When `p.everWin === 'yes'` and `recentWin == null`, add a warn. For a 비규제 민영, push nothing, or a note at most.

### SP-02 · HIGH · 특별공급 1회 제한 (제55조) is never part of the verdict
- **Current code:** No special-supply history field is used in spJudge. The everWin question (L3112) covers "특별공급·일반공급·무순위 모두". The only mention is an informational row in the 부적격 방지 card (L2441: "이 서비스는 이 이력을 판정하지 않으니…"). The verdict can still be "가능".
- **Official rule:** 제55조 "제35조부터 제49조까지의 규정에 따른 특별공급은 한 차례에 한정하여 1세대 1주택의 기준으로 공급한다". 2026000409: "…특별공급을 받은 분 및 그 세대에 속한 분은 특별공급을 받은 것으로 간주하므로 특별공급에 신청할 수 없습니다 (단, 제55조 및 제55조의3을 적용하는 경우는 제외)".
- **Failure scenario:** A household member won 생애최초 in 2019. The user says everWin = '있어요' and recentWin = '아니요' (the 재당첨 period has ended). Every special-supply type shows "가능". If they apply and win, it is 부적격.
- **Fix:** If `everWin === 'yes'`, warn "특별공급 당첨 이력이면 신청 불가 (예외: 배우자 혼인 전 이력[신혼·생애최초·신생아], 혼인특례[신혼], 출산특례[‘24.6.19 이후 출생 자녀, 신혼·신생아·다자녀·노부모])". Better: add a yes/no question about special-supply wins and judge it. `everWin === 'none'` is enough to show "해당 없음".

### SP-03 · HIGH · 공공 생애최초 / 노부모 1순위 is hard-coded to 12개월·12회
- **Current code:** In SP_RULES.public, `first: { head:'no', acct:'12x12' … }` and `elder: { head:'yes', acct:'12x12' … }` (L1791, L1793). spJudge L1884-1886: `nm = R.acct === '12x12' ? 12 : 6; need(m >= nm …); need(p.acctCount >= nm …)`. For public types it never calls accountItems/publicItems or regulatedItems. Yet publicItems (L637) already uses `L.depositCount || (L.regulated ? 24 : L.capital ? 12 : 6)` for general supply.
- **Official rule:** 제43조①1 (국민 생애최초) "제27조제1항의 1순위에 해당하는 무주택세대구성원으로서 저축액이 … 600만원 이상". 제46조①1 (노부모) "제27조 및 제28조에 따른 제1순위". 제27조①1:
  - 가. 수도권: 1년·12회
  - 나. 수도권 외: 6개월·6회
  - 다. 투기과열지구·청약과열지역: "2년이 지난 자로서 … 24회 이상", "세대주일 것", "과거 5년 이내 무주택세대구성원 전원이 다른 주택의 당첨자가 되지 아니하였을 것"

  The "1년·12회" in 2026000409 ("입주자저축 1순위(1년이 경과한 자로서 … 12회 이상)") is the 수도권 비규제 case only.
- **Failure scenarios:**
  - (a) An LH 공공분양 in 서울 / 과천 / 하남 / 성남 (투기과열 since 2025-10-15): a user with 15회, or who is a 세대원, or whose household won within 5 years, gets 생애최초 "가능". That is a false 가능.
  - (b) An LH 공공분양 outside 수도권 with 8회 gets "납입 인정 12회 미만 → 불가". That is a false 불가.
- **Fix:** For R.acct '12x12', use `L.depositCount || (L.regulated ? 24 : L.capital ? 12 : 6)` for both months and count. When `L.regulated`, also require 세대주 and the 5년 내 당첨 없음 check, reusing regulatedItems-style logic with `p.win5y`. Add boundary cases to tools/make_judge_cases.py.

### SP-04 · MEDIUM · '무주택 세대 · 입력 필요' is treated as 무주택 OK
- **Current code:** L1865 `need(home ? (home.hhUnknown ? null : home.s !== 'fail' && !home.owns) : null, '무주택 세대', …)`. When eligibility() returns `{k:'무주택 세대', s:'warn', v:'입력 필요'}` (L1051, which happens when selfOwn == null or household is empty), hhUnknown is undefined, so the condition evaluates true and spJudge records ok '무주택 세대'.
- **Official rule:** 무주택세대구성원 is a requirement for every type (제35조의3, 제40·41·43·46조).
- **Failure scenario:** A user fills in 혼인/소득/통장/자녀 but not "집 보유". 민영 신혼부부 (head 'no') can come out "가능" with no warning about home ownership.
- **Fix:** `home.s === 'warn' && !home.owns ? null : …`. Better: map ok → true, fail or owns → false, and anything else → null.

### SP-05 · MEDIUM · Account type is not checked in the non-1순위 special-supply path
- **Current code:** In the L1884-1888 else-branch (민영 '6m', 공공 '6x6' / '12x12'), only months, count or 예치금 are checked. The checks for 통장 종류 (청약저축 → 민영 불가; 청약부금 → 85㎡ 초과 불가; 청약예금·부금 → 공공 불가, see publicItems L638-640) exist only inside accountItems/publicItems. Those are reached only for acct 'r1'.
- **Official rule:** 2026000443 청약통장 자격요건: "다자녀가구 / 신혼부부: ① 청약예금 … ② 청약부금 … (85㎡ 이하에 한함) ③ 주택청약종합저축" (청약저축 is not listed). 2026000414/409: LH 공공분양 must use 주택청약종합저축 (전환 필요).
- **Failure scenario:** A 청약저축 holder looks at a 민영 신혼부부 or 다자녀 listing. They get "가능" if the months and 예치금 pass.
- **Fix:** In the else-branch, push the same 통장 종류 fail items: the minyoung saving/bugeum checks and the public non-'all' check.

### SP-06 · MEDIUM · 공공 신혼부부: the "혼인 7년 이내 *또는* 6세 이하 자녀" path is missing
- **Current code:** L1896 `need(p.marriedOn ? p.marriedOn >= addYears(ref, -7) : null, '혼인 7년 이내', '혼인 7년 초과', …)` is applied to 공공 as well.
- **Official rule:** 2026000409, 0414, 0416 and 0437 신혼부부 ① define 신혼부부 as "혼인 중인 사람으로서 혼인기간이 7년 이내(…)이거나 6세 이하(만 7세 미만을 말함) 자녀를 둔 무주택세대구성원".
- **Failure scenario:** Married in 2018 with a child born in 2021, applying to an LH 공공분양 (공고 2026-08-26). The app says "혼인 7년 초과 → 불가" (false 불가). They actually qualify as 1순위 (혼인기간 중 출산 미성년 자녀).
- **Fix:** For pub, pass when married and (≤7y or youngestBirth > ref − 7y, i.e. under 만 7세). For the 혼인기간 점수 (pubPoints L2021) a >7y marriage gets 0, which is already right.

### SP-07 · MEDIUM · 공공 신혼부부: 예비신혼부부 and 한부모가족 are judged 불가
- **Current code:** L1895 `if (!p.married) fail.push(pub ? '혼인 7년 이내 아님 (예비신혼부부·한부모는 공고문 확인)' : '혼인 중 아님')`. The verdict is '불가' even though the text says to check the notice.
- **Official rule:** 2026000409 신혼부부 ① "…, 예비신혼부부[혼인을 계획 중이며 … 입주 전까지 혼인사실을 증명 …], 한부모가족[6세 이하(만 7세 미만) 자녀(태아를 포함)를 둔 무주택세대구성원]". Its 선정순위 lists "1순위 ③ 6세 이하 자녀를 둔 한부모가족 / 2순위 ① 예비신혼부부".
- **Failure scenario:** An unmarried parent with a 3-year-old, or an engaged couple, is told 신혼부부 특공 "불가" on LH listings (false 불가). The about-page says these groups are "판정하지 않음" (L3234), which contradicts the hard 불가.
- **Fix:** For pub && !married, use warn (확인 필요), or a pass when kids under 7 exist (한부모), instead of fail. Ideally add questions for 예비신혼 and 한부모.

### SP-08 · MEDIUM · 민영 생애최초 '1인 가구' is keyed on hhSize instead of "혼인 중 아님 + 미혼 자녀 없음"
- **Current code:** L1900 `const single = !p.married && !(kids > 0) && p.hhSize === 1;`. L1902 only warns when unmarried with no kids and hhSize ≠ 1. L1948-1949 forces '추첨 (1인 가구)' only when hhSize === 1. Otherwise the stage loop can return '우선공급 (50%)'.
- **Official rule:** 제43조③2나 and ④1·2 ("제2호나목은 제외"): unmarried people without children are in the 추첨 stage only. 2026000103/0443 "1인 가구(혼인 중이 아니면서 미혼인 자녀도 없는 분)는 추첨제로만 신청가능하며, '단독세대'와 '단독세대가 아닌 분'으로 구분 … '단독세대가 아닌 분'이란, 직계존속과 같은 세대를 구성하는 경우" (only 단독세대 is limited to 60㎡). The rule also counts any 미혼 자녀, not only minors (app uses kidsMinor).
- **Failure scenarios:**
  - An unmarried person with no kids living with parents (hh 3) is shown "우선공급 (50%) 대상" (verdict 확인 필요). They can only enter the 추첨.
  - An unmarried parent with a 20-year-old unmarried child on the 등본 is treated as 1인 → "1인 가구는 전용 60㎡ 이하만" (false 불가 on >60㎡).
- **Fix:** Define 1인 가구 = `!married && !(unmarried children incl. adult)`. Force the stage to 추첨 for every 1인 가구. Apply the 60㎡ limit only to 단독세대 (no 직계존속 on the 등본).

### SP-09 · MEDIUM · 공공 소득 basis: the app asks "작년 세전 소득", but LH judges by 사회보장정보시스템 (보수월액 etc.)
- **Current code:** spIncome L1804-1808 uses `hhIncomeYear` / `income` / `spouseIncome`, labelled "(작년)" (L3099-3100), for both 민영 and 공공.
- **Official rule:** 2026000409 4. 소득기준: "사회보장정보시스템을 통해 '<표6> 조회대상 소득항목 및 소득자료 출처'에 따라 조사 확정 … 공고일 이후 변동된 소득금액이 조회된 경우 해당 금액을 당사자의 소득금액으로 간주". 상시근로소득 반영순위 ① 국민건강보험공단(보수월액). 민영 notices instead use "전년도 소득" (2026000103 소득확인시점), which matches the app.
- **Failure scenario:** A worker whose current 보수월액 is higher than last year's 총급여/12 (raise, job change) gets 공공 신혼 "우선공급 가능". LH would find them over the limit.
- **Fix:** For pub, label the income as current monthly income (건강보험 보수월액 기준) and mark it '추정'. Or warn that 공공 uses current 보수월액 plus other income types (사업·재산·공적이전).

### SP-10 · LOW · 생애최초 extra conditions not modelled
- (a) The rule requires being "근로자 또는 자영업자(과거 1년 내에 소득세를 납부한 자를 포함)" at the 공고일, plus 5 years of tax (제43조①3, ③3). taxYears5 (L1899) asks only about the 5 years, so an unemployed person with no tax in the past year gets a false 가능.
- (b) 제55조의3 / 2026000409 ①: a spouse's 혼인 전 ownership that was disposed of before marriage is excluded. The question "세대원 모두 … 집을 가진 적이 없나요?" (L3104) has no exception, so this case gets a false 불가.
- (c) 공공 생애최초 저축액 600만: the app compares `acctPaid`, which the app defines as the 25만/회-capped 인정 금액 (L3070). Whether 600만 is measured by capped 인정금액 or by actual 저축액 (선납금 포함) could not be verified from local sources (see Unverifiable).

### SP-11 · LOW · 노부모: the dependent's spouse living in a separate household is not checked
- **Current code:** L1910 fails only when `household==='parents' && parentsOwn` or `hhOwner === 'parent60'`.
- **Official rule:** 제46조①2 "피부양자의 배우자도 무주택자이어야". 2026000409 ⑤ example 1: "세대분리 된 부(父)가 단독주택을 소유 … 신청 불가".
- **Failure scenario:** The applicant supports their 70-year-old mother on the same 등본. The father lives separately and owns a house. The app says "가능".
- **Fix:** Add a question about whether the dependent parent's spouse owns a home, or always warn.

### SP-12 · LOW · 신생아: an older youngestBirth with the pregnancy question unanswered gives 불가
- L1893: `p.pregnant === true ? true : (young ? born : …)`. If the youngest child is 3 and `pregnant == null`, the result is fail. Pregnancy (태아) would qualify (제35조의3①3), so this should be warn (null) when `pregnant == null`.

### SP-13 · LOW · pubPoints details
- (a) The income point (L2016) ignores 출산가구 완화. The 2026000409/0414 점수표 says "※ 출산가구 소득기준 완화 … <표5> 참조".
- (b) 혼인기간 (L2021) uses floor months, so 3년 + 20일 counts as "≤3" and gets 3점 instead of 2점 ("3년 이하" / "3년 초과 5년 이하"). The same floor issue applies to the 5/7-year cut-offs. These are score overstatements only.

### SP-14 · LOW · mcScore 무주택기간 ignores the spouse's ownership history
- L1970-1973 uses only `p.homeSoldOn` (self). 2026000103 배점표 ④: "청약신청자 또는 배우자가 주택을 소유한 사실이 있는 경우에는 그 주택을 처분한 후 무주택자가 된 날부터". 2026000409: the 배우자 혼인 전 이력 is ignored, but post-marriage ownership counts (예3).
- Result: a spouse who sold a house after the marriage leaves the score overstated by up to 10점.

### SP-15 · LOW (conservative) · 출산특례 (제55조의3③) not modelled
- 2026000443: a past special-supply winner with a child born after '24.6.19 may apply to 다자녀/신혼/노부모/신생아. They may do so even while owning a home, on condition of selling it. The app always gives "무주택 세대 아님 → 불가" (false 불가). This is low risk because the error is on the safe side.

### SP-16 · LOW · Type availability edge cases
- spTypesFor L1801: when 청약홈 has no per-type breakdown, all 5 types are judged. That includes 민영 신혼/생애최초/신생아 on >85㎡ types, which the rules limit to 85㎡ 이하 (제35조의3③, 제41조①, 제43조③).
- supplySummary L2543: "이 주택형은 특별공급 없음" is shown when only 기관추천 units exist. 기관추천 is otherwise correctly disclosed as not judged (L3234).

### SP-17 · LOW · 민영 신혼 순위 label
- spPosition L2047 marks "1순위 (혼인 중 자녀)" for any minor child or pregnancy. 2026000103 says "현재 혼인관계에 있는 배우자와의 혼인기간 내 출산(태아, 입양자녀 포함)한 미성년 자녀가 있는 경우에만 1순위". Children born before the marriage or from a prior marriage are 2순위. Only the position text is affected.

### SP-18 · LOW (side note, general supply) · recentWin fails 비규제 민영 too
- eligibility L1085 fails any listing when recentWin is true. 제54조① excludes "투기과열지구 및 청약과열지역이 아닌 지역에서 공급되는 민영주택" from the 재당첨 restriction. This is a false 불가 on 비규제 민영 general supply. It is mentioned for consistency with the SP-01 fix.

---

## Verified correct
- **SP_INCOME_2025:** [7,533,763; 8,802,202; 9,326,985; 9,906,263; 10,485,541; 11,064,819] and SP_PER_PERSON 579,278 match the 2025 tables in all 31 local notices with special supply (grep). spAmt rounding reproduces 130% 3인 이하 = 9,793,892, 200% = 15,067,526, etc. (2026000409 표4).
- **SP_ASSET:**
  - 민영 3억3,100만: 2026000103/0443
  - 공공 부동산 215,500천원 / 자동차 45,420천원: 2026000409 <표2>
  - 출산가구 완화 237,050/258,600천원 · 49,960/54,510천원: <표3> and L1941
- **Income stages and percentages per type:**
  - 민영 신혼 100/120 → 140/160 → 추첨 (+ "부부 중 1인 소득 100%/140% 이하"). The 1인 소득 rule is not in the 2026.6.15 rule text (제41조③), but it is still printed in every 2026 민영 notice (0103 L939/941, 0443, 0453, 0399, 0403), so keeping it is correct.
  - 민영 신생아 / 생애최초: 130 → 160 → 추첨 (제35조의3④, 제43조④)
  - 공공 신생아: 100/120, 140/150, 140/200
  - 공공 신혼 / 생애최초: 100/120, 130/140, 130/200
  - 공공 다자녀 / 노부모: 120/130, 120/200 (all from 2026000409 표4)
- **Asset test placement:** 민영 only at the 추첨 stage; 공공 is an eligibility requirement plus 자동차.
- **Boundaries:**
  - 신생아 "2세 미만(2세가 되는 날을 포함)": `young >= addYears(ref,-2)` includes the 2nd birthday (제35조의3①3, ③3).
  - 신혼 7년: `marriedOn >= addYears(ref,-7)` matches "2019.08.26.~2026.08.26.에 속한 자" for 공고 2026-08-26.
- **birthRelax:** ’23.3.28 이후 (태아 포함) 1명 = +10%p; 2명 이상, including 1 after plus 1 before, = +20%p, matching 2026000409. relaxRange correctly avoids a hard 불가.
- **hhCount:**
  - 민영 (all types) and 공공 생애최초: 직계존속 only if 1년 이상 on the same 등본; 태아 counted (2026000103/0443/0409 가구원수 기준)
  - 공공 신혼·다자녀·신생아·노부모: all 무주택세대구성원
- **Head (세대주) requirements:**
  - 민영 노부모: always (제46조①2)
  - 민영 신생아 / 생애최초: only via 1순위 in 규제지역 (2026000103 "주민등록표등본상 세대주")
  - 공공 노부모: always (2026000409 "세대주만 가능")
  - Not required: 민영/공공 신혼, 다자녀
- **Account requirements:**
  - 민영 신혼 / 다자녀: 6개월 + 예치금
  - 민영 신생아 / 생애최초 / 노부모: 1순위 via accountItems + regulatedItems (24개월, 세대주, 5년, 2주택 in 규제지역)
  - 공공 신혼 / 신생아 / 다자녀: 6개월·6회
- **노부모 60세 rule:** the 만 60세 이상 직계존속 주택 exception is correctly not applied (L1910; 제53조 단서).
- **다자녀 배점표 (mcScore):** 40/35/25, 15/10/5, 5, 20/15/10, 15/10/5 (수도권 = one 시·도), 5 (10년). Matches 2026000103 and 0409. Kids are counted as minors including 태아 / 입양.
- **공공 신혼 / 신생아 점수 (pubPoints):**
  - 소득 80% (맞벌이 100%) = 1
  - 자녀 3 / 2 / 1
  - 거주 3 / 2 / 1 / 0, by 시·군 or 특별·광역시
  - 납입 24 / 12 / 6 → 3 / 2 / 1
  - 혼인기간 3 / 2 / 1 / 0 (2026000409, 0414)
- **공공 생애최초:** 1인 가구 불가 (2026000409 / 0414 / 0416 "1인 가구의 경우 생애최초 특별공급 청약신청이 불가"); 저축 600만원 check present.
- **기관추천 / 이전기관 / 청년:** not judged, and this is disclosed in the 이용 안내 (L3234). spTypesFor does not invent them.

## Unverifiable with local sources
- 「공공주택 특별법 시행규칙」 별표6 text. WebFetch to law.go.kr was blocked (provenance). The 공공 rules here were checked against LH notices only. Whether 별표6 overrides 제27조 regional 1순위 lengths for 생애최초/노부모 (SP-03) is inferred from the 규칙 text. None of the local LH notices is in a 투기과열지구.
- 공공 생애최초 "저축액 600만원(선납금 포함)": whether it is measured as the capped 납입인정금액 or the actual deposit (SP-10c).
- 출산가구 소득 완화 <표5>: the per-stage table body (especially whether +10/20%p applies to the 추첨 200% line) was only partly captured in the text extraction. The app applies it to all stages.
- 2026000409 신생아 점수표 body (image in PDF). The app assumes 소득1 + 자녀3 + 거주3 + 납입3 = 10.
