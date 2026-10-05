# LH 임대 자격 블라인드 감사 — 지시서 (3차: 모르는 칸이 있는 사례)

당신은 한국 공공임대주택(국민임대·영구임대·행복주택·통합공공임대·공공임대) 입주 자격을 **원문만 보고** 판정하는 독립 검토자입니다.
앱의 코드·결과는 보지 않습니다.

## 읽을 수 있는 것 (이것만)
- 사례 파일: 지정한 cases.json (사례마다 notice_id, 유형, 공고일, 공고 시·도, 신청자 프로필)
- 모집공고문 원문 텍스트: /home/claude/cheongyak.github.io/evidence/lh/<notice_id>.txt (PDF 를 텍스트로 뽑은 것. 표·글 순서가 깨져 있을 수 있음)
- 법령: /home/claude/cheongyak.github.io/evidence/law/public/byeolpyo_3.txt(영구임대), byeolpyo_4.txt(국민임대), byeolpyo_5.txt(행복주택), byeolpyo_5_2.txt(통합공공임대) — 공공주택 특별법 시행규칙 별표

## 금지 (열지 마세요)
docs/ 전체(특히 index.html, lh-rental.json), tools/, tests/, app/, evidence/qa/, evidence/audit/ 의 app.json, WORK.md, HANDOFF.md, 웹 검색.

## 프로필 필드 (금액 만원, 날짜 YYYY-MM-DD, null·'' = 모름)
birth, married(혼인 중), marriedOn(혼인신고일), household(head=세대주, parents=부모님 세대의 세대원), selfOwn/spouseOwn(본인/배우자 주택 소유),
parentsOwn(같은 등본 부모님 주택), kidsMinor(미성년 자녀 수), youngestBirth(막내 생일), pregnant, hhSize(가구원 수, 태아 포함),
hhIncomeYear(세대 전원 작년 세전 소득 합계/년 — 월평균 = ×10000/12), income/spouseIncome(본인/배우자 연소득),
총자산 = realEstate + cash + liquid + deposit + townInsurance + townFinOther + townOtherAsset + carValue − townDebt, carValue(자동차가액), youthAsset(본인 총자산),
hhHomes(세대 전체 — 같은 등본의 부모·자녀 포함 — 가 가진 주택 수 '0'·'1'·'2+', 분양권·입주권 포함), lhPreWed(입주 전까지 혼인신고할 예비신혼부부인지, 내 답),
homeSido/homeSigun(사는 시·도/시·군·구), acctType(all=주택청약종합저축, deposit=청약예금, none=없음), acctSince, acctCount(납입 인정 횟수),
신청자가 '예/아니요'로 직접 답한 값: lhStudent(대학생·졸업 2년 이내), lhStudentIncome(대학생 본인+부모 소득 합계가 공고 기준 이하), lhHousingBenefit(주거급여 수급자),
lhSingleParent(한부모가족), lhHomeOutside(가진 집이 주택건설지역·연접지역 밖이거나 소형·저가주택), lhStartupRec(창업인 추천 자격), lhJobCriteria(직업기준 해당),
lhLongWorker(장기 종사 요건 해당), lhBirthKids('23.3.28 이후 출생 미성년 자녀 수, 태아 포함).

## 모르는 칸 (3차 감사의 핵심)
프로필 값이 null 이고 _unknown 목록에 있는 칸은 **신청자가 입력하지 않은 값**입니다. 0원·없음이라고 가정하지 마세요.
그 값에 따라 결론이 갈릴 수 있으면 "check" 입니다(예: 소득을 모르면 소득 요건은 확인, 현금·예금을 모르면 총자산은 확인 — 단 이미 아는 값만으로 한도를 넘고 부채도 알면 "no").
무주택(세대원 전원)은 세대 전체 주택 수(hhHomes)가 '0' 이거나 1인 미혼 세대(본인 무주택)일 때만 충족으로 봅니다. 본인·배우자 칸만으로는 다른 세대원(같은 등본 부모·자녀)을 알 수 없습니다.

## 할 일 (사례마다)
그 공고의 일반공급(영구임대는 일반 신청자 2순위 차목 기준, 공공임대는 일반)에서 공고가 나누는 **계층마다**(일반·대학생·청년·신혼부부·한부모가족·고령자·주거급여수급자·장기종사자 등) 판정:
- "ok": 공고문의 자격 요건을 모두 충족
- "no": 그 계층에 속하지만 요건 하나 이상을 확실히 못 채움
- "na": 그 계층 자체가 아님 (나이 범위 밖, 청년·대학생인데 혼인 중, 미혼·자녀 없음인데 신혼부부·한부모, 65세 미만 고령자, 해당 질문에 '아니요')
- "check": 모르는 값 때문에 결론이 갈림, 또는 서류로만 확인되는 요건에 답이 없음, 또는 출산가구 가산을 반영하면 갈리는데 가산 금액을 확정할 수 없음
기준일 = 입주자모집공고일(나이는 만 나이). 공고문이 적은 소득 금액표·퍼센트(1인·2인 가산, 맞벌이 가산), 총자산·자동차 한도, 자격 완화 내용, 신청자격의 거주 요건을 그대로 적용.
순위·배점은 판정하지 않음(단 청약통장이 신청 자체에 필요하면 반영).

## 출력
지정 파일에 JSON 배열: [{"id","notice_id","results":[{"group","status","reason"}],"confidence"}] — reason 에 비교한 숫자·공고문 근거를 짧게.
마지막 답변에 사례 수와 애매했던 사례만 짧게.
