// 코드 변이 검사 (2026-10-02 MASTER QA 12항): 판정·표시 코드에 일부러 오류를 하나씩 넣고(파일은 안 바꾸고 브라우저에 보낼 때만 바꿈)
// 판정 검증 사례(tests/judge/cases.json, 기대값은 tools/make_judge_cases.py 의 독립 계산)와 공급유형 표시 검사가 잡는지 센다.
// 잡지 못한 변이 = 그 규칙을 지키는 테스트가 없다는 뜻. 사용: NODE_PATH=$(npm root -g) node tools/qa/code_mutation.cjs → evidence/qa/code-mutation.json
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
const HTML = readFileSync(join(DOCS, 'index.html'), 'utf8');
const M = [   // [이름, 찾을 글, 바꿀 글]
  ['공공분양식 공공임대 특공: 출산 완화 2명 이상을 1명 금액으로 (2026000402)', "const lim = (base, arr) => add === 20 && RX ? arr[1] :", "const lim = (base, arr) => add === 20 && RX ? arr[0] :"],
  ['공공분양식 공공임대 특공: 자산 초과를 완화 확인으로 (2026000402)', "const maybe = (v, arr) => (add === null || (add === 10 && RX) || (add && !RX)) && (!RX || v <= arr[1]);", "const maybe = (v, arr) => true;"],
  ['무주택: 본인 주택을 무시', "if (p.selfOwn && !(exc && OWN_EXC_OK.includes(exc))) own.push('본인 명의 주택');", "if (false) own.push('본인 명의 주택');"],
  ['60㎡ 경계 > → >= (공공 소득·자산 없음 판단)', "if (!pl) return (L.area != null && L.area > 60)", "if (!pl) return (L.area != null && L.area >= 60)"],
  ['60㎡ → 59㎡ (생애최초 단독세대)', "if (alone && (L.area || 0) > 60)", "if (alone && (L.area || 0) > 59)"],
  // 동등 변이(EQUIVALENT): 소득은 만 원/년으로 입력해 월평균이 원 단위 기준액과 정확히 같아질 수 없다 (기준표 3인 이하~8인 × 50~259% 모두 확인, 2026-10-02) — 점수에서 뺌
  ['소득 기준 <= → < (공공 일반공급) [동등]', "if (m <= spAmt(n, cap)) out.push({ k:'소득 (공공 일반공급)'", "if (m < spAmt(n, cap)) out.push({ k:'소득 (공공 일반공급)'"],
  ['소득 기준 +1%', "if (m <= spAmt(n, cap)) out.push({ k:'소득 (공공 일반공급)'", "if (m <= spAmt(n, cap) * 1.01) out.push({ k:'소득 (공공 일반공급)'"],
  ['혼인 7년 → 8년 (신혼희망타운)', "if (p.marriedOn && p.marriedOn >= addYears(ref, -7)) out.push({ k:'신청 유형 (신혼희망타운)'", "if (p.marriedOn && p.marriedOn >= addYears(ref, -8)) out.push({ k:'신청 유형 (신혼희망타운)'"],
  ['자녀 만 6세 경계 하루 이동', "const kid6 = p.pregnant === true || (p.youngestBirth && p.youngestBirth > addYears(ref, -7));", "const kid6 = p.pregnant === true || (p.youngestBirth && p.youngestBirth >= addYears(ref, -7));"],
  ['거주기간 기준일 <= → <', "if (!R.since || since <= R.since) return { k, s:'ok', v:'해당지역 ('", "if (!R.since || since < R.since) return { k, s:'ok', v:'해당지역 ('"],
  ['통장 가입기간: 규제지역 24 → 12개월', "return [L.regulated ? 24 : L.capital ? 12 : 6, false];", "return [L.regulated ? 12 : L.capital ? 12 : 6, false];"],
  ['예치금 85㎡ 구간 <= → <', "ACCOUNT_DEPOSIT[g][a <= 85 ? 0 :", "ACCOUNT_DEPOSIT[g][a < 85 ? 0 :"],
  ['판정 묶음: 확인 필요를 가능으로', "return e.ok && !e.unsure ? 'ok' : e.ok ? 'unsure'", "return e.ok ? 'ok' : e.ok ? 'unsure'"],
  ['일반 0세대: 특공 0이면 불가 → 확인 필요', "if (u && u.total != null && !u.total) return 'no';", "if (u && u.total != null && !u.total) return 'unsure';"],
  ['일반 0세대: 거주지 불가를 무시 (2026-10-02 과천 84D) [동등]', "if (on('verdict_one') && spCommonFail(L, p).length) return 'no';", ''],
  ['마감일 하루 이동', "if (end && TODAY > end) return '마감';", "if (end && TODAY >= end) return '마감';"],
  ['공급유형: 재공급 배지를 무순위로', "/재공급/.test(L.supplyType || L.kind || '') ? '재공급' : '무순위'", "'무순위'"],
  ['공급유형: 일반공급 칸 재공급을 무순위로', "/재공급/.test(L.kind || '') ? '재공급' : '무순위'", "'무순위'"],
  // LH 임대 판정 (기능 lh_rental, 2026-10-05 사용자 '일반분양 수준 QA') — 판정 사례 lhrent-* 가 잡아야 한다
  // [동등] 표시: 일반 0세대 거주지 — spJudge 가 거주지·재당첨을 직접 본다(기능 supply_summary, 10-02 뒤) → 이 줄은 이중 안전장치라 빼도 결과가 같다.
  //            LH 통장 1순위 개월 — 지금 공공임대 공고 2건 모두 2순위(가입만)도 신청 가능해 1순위 경계가 자격 결론(ok)을 바꾸지 않는다(문구만 1순위/2순위).
  ['LH: 청년 39세 상한 +1', "(g.age_max != null && age > g.age_max)", "(g.age_max != null && age > g.age_max + 1)"],
  ['LH: 고령자 65 → 64', "else if (age < g.age_min) { na = true;", "else if (age < g.age_min - 1) { na = true;"],
  ['LH: 소득 기준 +1%', "else if (m <= lim) add('ok', '소득 ' + txt);", "else if (m <= lim * 1.01) add('ok', '소득 ' + txt);"],
  ['LH: 총자산 기준 +1만원', "else if (tot <= lim) add('ok', '총자산 ' + txt);", "else if (tot <= lim + 1) add('ok', '총자산 ' + txt);"],
  ['LH: 자동차 <= → <', "else if (Number(p.carValue) <= lim) add('ok'", "else if (Number(p.carValue) < lim) add('ok'"],
  ['LH: 대학생 자동차 소유 허용', "add(Number(p.carValue) > 0 ? 'no' : 'ok'", "add('ok'"],
  ['LH: 1인 가산 퍼센트 무시', "g.income_pct[n === 1 ? '1' : n === 2 ? '2' : '3+']", "g.income_pct[n === 2 ? '2' : '3+']"],
  ['LH: 신청자격 거주 시·도 무시', "else if (L0.sido && p.homeSido !== L0.sido) add('no'", "else if (false) add('no'"],
  ['LH: 거주 시·군 판단 불가를 일치로', "else if (sg === true) add('ok'", "else if (sg !== false) add('ok'"],
  ['LH: 출산 1명+형제 20 → 10', "Number(p.lhBirthKids) === 1 ? ((Number(p.kidsMinor) || 0) >= 2 ? 20 : 10) : 0", "Number(p.lhBirthKids) === 1 ? 10 : 0"],
  ['LH: 혼인 7년 → 8년', "const wf = T.sh ? g.wed_from : addYears(ref, -7)", "const wf = T.sh ? g.wed_from : addYears(ref, -8)"],   // 2026-10-06 SH 날짜 하한(wed_from)으로 코드가 바뀜
  ['LH: 맞벌이 가산 무시', "const dualAdd = dual && g.dual_add != null ? g.dual_add : 0;", "const dualAdd = 0;"],
  ['LH: 통장 1순위 개월 -1 [동등]', "mo >= A.months && Number(p.acctCount) >= A.count", "mo >= A.months - 1 && Number(p.acctCount) >= A.count"],
  ['LH: 미성년 19 → 18', "    else if (age < 19) {", "    else if (age < 18) {"],
  ['LH: 9인 이상 가산 무시', "(n - 8) * 579278", "(n - 8) * 0"],
  ['LH: 장기종사자 자녀 0 허용', "if (p.kidsMinor === 0) { na = true; add('no', '미성년 자녀가 없음 (미성년 자녀 포함", "if (false) { na = true; add('no', '미성년 자녀가 없음 (미성년 자녀 포함"],
  ['LH: 대학생 아니요 무시', "if (p.lhStudent === false) { na = true;", "if (false) { na = true;"],
  ['LH: 미성년 세대원 허용', "if (p.household && p.household !== 'head') add('no', '미성년 세대원", "if (false) add('no', '미성년 세대원"],
  ['LH: 청약예금 공공임대 허용', "add('no', '청약예금·부금으로는 신청 불가", "add('ok', '청약예금·부금으로는 신청 불가"],
  ['LH: 9인 이상 중위소득 가산 2배', "(n - 8) * Number(t.income_add_per)", "(n - 8) * 2 * Number(t.income_add_per)"],
  ['LH: 자격 완화 소득 배제 무시', "if (g.income_pct === 'excluded') { if (exclOk)", "if (g.income_pct === 'never') { if (exclOk)"],
  // 2026-10-05 안전성 점검(R3~R5): 모르는 것을 '가능'으로 만드는 경로를 되살리면 판정 사례가 잡아야 한다
  ['LH 안전: 미입력 기본값 0·false 를 입력으로 봄', "if (ZERO_KEYS.includes(k) && v === DEFAULT_PROFILE[k]) return Array.isArray(p._set) && p._set.includes(k);", ""],
  ['LH 안전: 빈 글자를 모름으로 보지 않음', "p = Object.fromEntries(Object.entries(p || {}).map(([k, v]) => [k, v === '' ? null : v]));", ""],
  ['LH 안전: 세대 주택 수 없이 무주택 확정', "else if (solo1) add('ok'", "else if (true) add('ok'"],
  ['LH 안전: 완화 아닌 미적용을 믿음', "const exclOk = T.relaxed === true || N.type === '공공임대' || g.exempt === true;", "const exclOk = true;"],
  ['LH 안전: 모르는 계층도 판정', "} else if (!['일반', '장기종사자'].includes(g.key)) {", "} else if (false) {"],
  ['LH 안전: 맞벌이 가산 기본값 30', "const dualAdd = dual && g.dual_add != null ? g.dual_add : 0;", "const dualAdd = dual ? (g.dual_add ?? 30) : 0;"],
  ['LH 안전: 예비신혼부부를 공고문 확인 없이', "else if (T.prewed_ok && p.lhPreWed === true) add('ok'", "else if (p.lhPreWed === true) add('ok'"],
  ['LH 안전: 출산 여부 모름을 아님으로', "const kidMaybe = rBirthKid(p) || !birthKnown;", "const kidMaybe = rBirthKid(p);"],
  ['LH 안전: 2호 이상 주택 수 모름 통과', "someoneOwns && T.homeless_relaxed && T.homeless_max1 && p.hhHomes !== '1') {", "someoneOwns && T.homeless_relaxed && T.homeless_max1 && p.hhHomes === '2+') {"],
  ['LH 안전: 입력 어긋남(0채인데 집) 무시', "if (p.hhHomes === '0' && owners > 0) add('check'", "if (false) add('check'"],
  ['LH 안전: 나이 기준 한쪽만 읽어도 통과', "else if (g.age_min == null || g.age_max == null) add('check', `청년 나이 기준 일부", "else if (false) add('check', `청년 나이 기준 일부"],
  ['LH 안전: 총자산 빠진 칸 무시', "else if (miss.length) add('check', '총자산 입력 필요", "else if (false) add('check', '총자산 입력 필요"],
  ['LH 안전: 거주 요건 못 읽음 무시', "if (!T.local && T.local_unread) add('check'", "if (false) add('check'"],
  ['LH 안전: 공공임대 통장 요건 못 읽음 무시', "if (N.type === '공공임대' && T.account == null) add('check'", "if (false) add('check'"],
  ['LH 안전: 소득 미입력을 본인 소득 0으로', "const yearMan = youthMember ? inc : hhInc != null ? hhInc : solo ? inc : null;", "const yearMan = youthMember ? (inc || 0) : hhInc != null ? hhInc : solo ? (inc || 0) : null;"],
  ['예치금 빈칸을 0원으로 (2026-10-06 제보, 체크리스트)', "amt = pv(p, 'acctAmount');   /* 예치금 칸을", "amt = p.acctAmount || 0;   /* 예치금 칸을"],
  ['예치금 빈칸을 0원으로 (2026-10-06 제보, 특별공급·순위)', "amt = pv(p, 'acctAmount'); need(", "amt = p.acctAmount || 0; need("],
  ['빈칸: 배우자 집 답 안 함을 없음으로', "else if (!own.length && p.married === true && !entered(p, 'spouseOwn'))", "else if (false)"],
  ['빈칸: 배우자 소득 모름을 외벌이로', "const dualUnknown = p => !!(p.married && p.income > 0 && !entered(p, 'spouseIncome'));", "const dualUnknown = p => false;"],
  ['빈칸: 세대 소득·배우자 소득 모름을 본인 소득으로 추정', "if (hasHh) return true; if (p.married && !entered(p, 'spouseIncome')) return false;", "if (hasHh) return true;"],
  ['빈칸: 현금 등 하나도 안 넣음을 0원으로', "if (!['cash', 'liquid', 'deposit'].some(f => entered(p, f))) miss.push(", "if (false) miss.push("],
  // SH 임대 자격 (기능 sh_judge, 2026-10-06) — 공고문 날짜 하한·출산가구 표·면제·세대 소득
  ['SH: 신생아가구 출생일 하한 하루 밀림', "else if (p.youngestBirth && p.youngestBirth >= bf) add('ok'", "else if (p.youngestBirth && p.youngestBirth > bf) add('ok'"],
  ['SH: 혼인신고일 하한 하루 밀림', "const in7 = p.marriedOn && ref && wf ? p.marriedOn >= wf : null", "const in7 = p.marriedOn && ref && wf ? p.marriedOn > wf : null"],
  ['SH: 출산가구 표 금액 무시', "else if (tbl && tbl[String(bo)] != null) {", "else if (false) {"],
  ['SH: 지원대상 한부모 검증 면제 무시', "N.type === '공공임대' || g.exempt === true;", "N.type === '공공임대';"],
  ['SH 행복주택: 사회초년생 나이 무관 무시', "      if (g.newcomer) add('check',", "      if (false) add('check',"],
  ['SH 행복주택: 사회초년생을 나이 안으로 봄', "      if (g.newcomer) add('check', `만", "      if (g.newcomer) add('ok', `만"],
  ["SH 청년안심: 3순위 넘으면 2·1순위 확인 무시(소득)", "else if (g.tier_note) add('check', '본인 소득이", "else if (false) add('check', '본인 소득이"],
  ["SH 청년안심: 본인 기준 소득 무시", "const youthMember = g.key === '청년' && (g.self_basis === true ||", "const youthMember = g.key === '청년' && (false ||"],
  ["SH 청년안심: 신혼부부 신청자 나이 무시", "if (!['청년', '고령자', '대학생'].includes(g.key) && (g.age_min != null || g.age_max != null)) {", "if (false) {"],
  ["SH 청년안심: 청년 출산 가산 없음 무시", "&& g.birth_bonus !== 'none', aTbl", ", aTbl"],
  ["SH 청년안심: 2순위 총자산 한도 무시", "else if (g.tier_note && g.tier_asset != null && Number(p.youthAsset) <= g.tier_asset)", "else if (g.tier_note && g.tier_asset != null)"],
  ["공공임대 공공분양식 표: 출산가구 완화 무시", "inc.forEach(i => { if (i.s === 'fail' && hi > 0)", "inc.forEach(i => { if (false)"],
  ["공공임대 공공분양식 표: 부동산 기준 무시", "pubLimits: { cap: pl.eligible.base.slice(), real_estate: pl.real_estate, car: pl.car", "pubLimits: { cap: pl.eligible.base.slice(), real_estate: 1e9, car: pl.car"],
  ["공공임대 공공분양식 표: 3인 이하 공통 금액 사용", "const inc = totalGeneralItems(L, p, Object.assign({}, pl, { kind: 'total', total_asset: 1e9 }))", "const inc = totalGeneralItems(L, p, Object.assign({}, pl, { kind: 'total', total_asset: 1e9, amounts: { elig: Object.fromEntries(Object.entries(pl.amounts.elig).map(([k, v]) => [k, Number(k) <= 3 ? [8168429, 16336858] : v])), pri: pl.amounts.pri } }))"],
  ['SH: 소득에 출산가구 가산 적용', "else if (kidMaybe && (!T.birth_bonus || (T.income_birth && !dual)) && m <=", "else if (kidMaybe && m <="],
  ['SH 장기전세: 출산가구 소득 가산 무시', "(!T.birth_bonus || (T.income_birth && !dual))", "!T.birth_bonus"],
  ['SH 장기전세: 의정부시 거주 예외 무시', "else if (L0.sido && p.homeSido !== L0.sido && L0.extra", "else if (false && L0.extra"],
  ['계약금: 공고문 비율 무시', "contractRate:on('contract_from_notice') && x.pay_ratio ? x.pay_ratio.contract :", "contractRate:false ? 0 :"],
  ['계약금: 같은 금액을 부족으로', "contractOk: cashNow >= contractAmt - 1e-9", "contractOk: cashNow > contractAmt"],
  ['SH 사회주택: 서울 밖 신청 가능 문장 무시', "else if (L0.sido && p.homeSido !== L0.sido && L0.others_check)", "else if (false && L0.others_check)"],
  ['SH 사회주택: 1인 가구 가구원 수 무시', "else if (Number(p.hhSize) !== 1) { na = true;", "else if (false) { na = true;"],
  ['SH 사회주택: 공고문 모집 공고일 대신 게시일', "const ref = (N.terms && N.terms.ref_date) || N.posted", "const ref = N.posted"],
  ['SH 사회주택: 혼인 기간 하루 밀림', "p.marriedOn >= addYears(ref, -g.wed_years)", "p.marriedOn > addYears(ref, -g.wed_years)"],
  ['SH 장기전세: 면적 묶음을 모르는 계층으로', "'일반', '장기종사자', '일반·60이하', '일반·60초과'].includes(g.key)", "'일반', '장기종사자'].includes(g.key)"],
  ['SH: 청년 세대 소득 대신 본인 소득', "&& !g.married_ok && !g.income_household;   /* SH 청년", "&& !g.married_ok;   /* SH 청년"],
  ['SH: 청년 세대 주택 조회 무시', "else if (sOwn === false && g.hh_home_scan && ((p.household", "else if (false && ((p.household"],
  ['SH: 6세 이하 자녀 하한 하루 밀림', "T.sh ? (g.kid6_from ? d >= g.kid6_from : null)", "T.sh ? (g.kid6_from ? d > g.kid6_from : null)"],
];
(async () => {
  const cases = JSON.parse(readFileSync(join(ROOT, 'tests/judge/cases.json'), 'utf8'));
  const listings = JSON.parse(readFileSync(join(ROOT, 'tests/judge/listings.json'), 'utf8'));
  const lhNotices = existsSync(join(ROOT, 'tests/judge/lh_notices.json')) ? JSON.parse(readFileSync(join(ROOT, 'tests/judge/lh_notices.json'), 'utf8')) : [];
    lhNotices.push(...(existsSync(join(ROOT, 'tests/judge/sh_notices.json')) ? JSON.parse(readFileSync(join(ROOT, 'tests/judge/sh_notices.json'), 'utf8')) : []));   // 기능 sh_judge
    lhNotices.push(...(existsSync(join(ROOT, 'tests/judge/lh_synthetic.json')) ? JSON.parse(readFileSync(join(ROOT, 'tests/judge/lh_synthetic.json'), 'utf8')) : []));   // 공고문을 잘못 읽은 경우 모의 (make_judge_cases)
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const out = [];
  for (const [name, find, repl] of [['(변이 없음 — 기준선)', '', ''], ...M]) {
    const n = find ? HTML.split(find).length - 1 : 0;
    if (find && n !== 1) { out.push({ name, status: 'NOT_TESTABLE', note: `찾을 글이 ${n}번 나옴 — 코드가 바뀜, 변이 목록 고칠 것` }); continue; }
    const html = find ? HTML.replace(find, repl) : HTML;
    const page = await b.newPage(); const errs = []; page.on('pageerror', e => errs.push(e.message));
    await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
      if (u.pathname === '/' ) return r.fulfill({ status: 200, body: html, contentType: 'text/html' });
      const f = join(DOCS, decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
      r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
    await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
    const r = await page.evaluate(({ cases, listings, lhNotices }) => {
      const byId = Object.fromEntries(listings.map(x => [x.id, fromApi(x)])); let bad = 0;
      const lhById = Object.fromEntries(lhNotices.map(x => [x.id, x]));
      for (const c of cases) { const L = byId[c.listing]; S.profile = Object.assign({}, DEFAULT_PROFILE, c.profile); save(); const p = S.profile; let got;
        try {
          if (c.fn === 'score') got = { parts: myScore(L, p).parts.map(x => x.v) };
          else if (c.fn === 'sp') { const q = spJudge(L, p, c.type); got = { s: q.s, ...(c.expect.stage ? { stage: q.stage ? q.stage[0] : null } : {}) }; }
          else if (c.fn === 'acct') { const it = accountItems(L, p) || []; got = { '가입기간': (it.find(i => i.k === '청약통장 가입기간') || {}).s, '예치금': (it.find(i => i.k === '예치금 (민영)') || {}).s }; }
          else if (c.fn === 'pubgen') { const it = pubGeneralItems(L, p); got = { '소득': (it.find(i => i.k.startsWith('소득')) || {}).s }; }
          else if (c.fn === 'town') { const it = townItems(L, p); got = {}; for (const k of Object.keys(c.expect)) got[k] = (it.find(i => i.k === k + ' (신혼희망타운)') || {}).s; }
          else if (c.fn === 'bucket') got = { b: eligBucket(L, p) };
          else if (c.fn === 'item') { const it = c.item === '거주지' ? residenceItem(L, p) : eligibility(L, p).items.find(i => i.k === c.item); got = { s: it ? it.s : 'none' }; }
          else if (c.fn === 'home') { const it = eligibility(L, p).items.find(i => i.k === '무주택 세대') || {}; got = { s: it.s }; }
          else if (c.fn === 'residence') { const q = residenceItem(L, p); got = { s: q.s, v: q.v.startsWith(c.expect.v) ? c.expect.v : q.v }; }
          else if (c.fn === 'contract') { const F0 = CONFIG.features; CONFIG.features = Object.assign({}, F0, { contract_from_notice: c.feature });
            try { const L2 = fromApi(c.raw), f = funding(L2, p, planOpt(L2)); got = { amt: Math.round(f.contractAmt * 10000), ok: f.contractOk, mid: L2.midRate }; } finally { CONFIG.features = F0; } }
          else if (c.fn === 'lhrent') { const q = rentalJudge(lhById[c.notice], p); got = {}; for (const k of Object.keys(c.expect)) got[k] = (q.groups.find(g => g.key === k) || {}).s; }
        } catch (e) { got = { error: e.message }; }
        if (JSON.stringify(got) !== JSON.stringify(c.expect)) bad++; }
      // 공급유형 표시: 불법행위 재공급 주택형의 카드 배지·일반공급 칸 이름에 '무순위'가 나오면 잡힌 것
      const re = LISTINGS.filter(L => /재공급/.test(L.supplyType || '')); let disp = 0;
      re.forEach(L => { const d = document.createElement('div'); d.innerHTML = cardBadges(L); if (/무순위/.test(d.innerText) || genLabel(L) === '무순위') disp++; });
      // 마감 상태: 접수 끝 날짜 = 오늘인 공고는 '접수 중'이어야 한다
      const st = statusOf({ apply: TODAY, applyEnd: TODAY }) === '접수 중' ? 0 : 1;
      return { bad, disp, st };
    }, { cases, listings, lhNotices });
    await page.close();
    const caught = r.bad + r.disp + r.st + errs.length;
    out.push({ name, status: find ? (caught ? 'KILLED' : name.includes('[동등]') ? 'EQUIVALENT' : 'SURVIVED') : (caught ? 'BASELINE_FAIL' : 'BASELINE_OK'), judge_fail: r.bad, display_fail: r.disp, status_fail: r.st, page_errors: errs.length });
    console.log(out[out.length - 1].status.padEnd(14), name, JSON.stringify(r));
  }
  await b.close();
  const mut = out.filter(o => o.name[0] !== '('), killed = mut.filter(o => o.status === 'KILLED').length, surv = mut.filter(o => o.status === 'SURVIVED').length;
  const rep = { date: new Date().toISOString().slice(0, 10), mutations: mut.length, killed, survived: surv, not_testable: mut.filter(o => o.status === 'NOT_TESTABLE').length, equivalent: mut.filter(o => o.status === 'EQUIVALENT').length, score: +(killed / Math.max(1, killed + surv)).toFixed(3), results: out };
  writeFileSync(join(ROOT, 'evidence/qa/code-mutation.json'), JSON.stringify(rep, null, 1) + '\n');
  console.log(`변이 ${mut.length} · 잡음 ${killed} · 못 잡음 ${surv} · 점수 ${rep.score}`);
  process.exit(surv ? 1 : 0);
})();
