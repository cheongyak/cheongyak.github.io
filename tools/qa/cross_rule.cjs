// 교차 규칙 모순 검사 (Cross-Rule Contradiction Detector, 2026-10-02 사용자 추가 MASTER QA).
// 각 값이 맞는지(필드 검사)가 아니라, 같은 공고의 값·판정·계산·화면 문구를 함께 놓았을 때 서로 모순되지 않는지 본다.
// 규칙 목록·근거·의존 관계: evidence/qa/CROSS_RULES.md (규칙 ID 가 같다). 이 도구는 법률 판단을 새로 만들지 않고, 이미 확인된 사실(공고문·수집값)과
// 서비스가 보여 준 결과끼리 충돌하는지만 검출한다. 모르는 사실(null)은 '모름'으로 전파되는지 본다.
// 대상: 지금 공고 전부 + 판정 사례 고정 공고(tests/judge/listings.json) × 판정 사례 조건 40개 + 유주택 조건 2개.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/cross_rule.cjs → evidence/qa/cross-rule.json, CRITICAL·HIGH 충돌이 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
(async () => {
  const cases = JSON.parse(readFileSync(join(ROOT, 'tests/judge/cases.json'), 'utf8'));
  const fx = JSON.parse(readFileSync(join(ROOT, 'tests/judge/listings.json'), 'utf8'));
  const profiles = [...new Map(cases.map(c => [JSON.stringify(c.profile), c.profile])).values()].filter((_, i) => i % 3 === 0).slice(0, 40);
  const base = profiles[0];
  profiles.push(Object.assign({}, base, { selfOwn: true, hhHomes: '1', hhNeverOwned: false }), Object.assign({}, base, { selfOwn: false, hhHomes: '2+', hhOwner: 'other', hhNeverOwned: false }));
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage({ viewport: { width: 390, height: 844 } }); const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(400);
  await page.evaluate(() => new Promise(res => { loadRental(); const t = setInterval(() => { if (RENTAL || RENTAL_STATE === 'error') { clearInterval(t); res(); } }, 50); }));   // LH 임대 (기능 lh_rental)
  const lhProfiles = [...new Map(cases.filter(c => c.fn === 'lhrent').map(c => [JSON.stringify(c.profile), c.profile])).values()];
  // 다른 조건은 모두 충족하는 사람 × 사는 곳(시·도·시군) — 거주 요건 규칙이 실제로 걸릴 수 있게 (변이 검사에서 놓친 것 보완)
  const LH_OK = { birth: '1994-03-01', married: false, selfOwn: false, household: 'head', hhSize: 1, hhIncomeYear: 1500, income: 1500, spouseIncome: 0, realEstate: 0, carValue: 0, cash: 500, liquid: 0, deposit: 0,
    townInsurance: 0, townFinOther: 0, townOtherAsset: 0, townDebt: 0, youthAsset: 500, kidsMinor: 0, eldersOnDeed: 0, hhHomes: '0', acctType: 'all', acctSince: '2015-01-01', acctCount: 60, lhBirthKids: 0 };
  for (const [sido, sigun] of [['서울', '마포구'], ['부산', '해운대구'], ['경남', '창원시'], ['경남', '김해시'], ['전북', '군산시'], ['전북', '전주시'], ['경기', '양주시'], ['경기', '수원시'], ['강원', '춘천시']])
    lhProfiles.push(Object.assign({}, LH_OK, { homeSido: sido, homeSigun: sigun }));
  const out = await page.evaluate(([profiles, fx, lhProfiles]) => {
    const seen = new Set(LISTINGS.map(L => L.id));
    fx.forEach(x => { if (!seen.has(x.id)) { const L = fromApi(x); L._fixture = true; LISTINGS.push(L); } });
    const txt = () => document.querySelector('#app') ? document.querySelector('#app').innerText : document.body.innerText;
    const V = [], stat = {}, B = { ok:'ok', unsure:'warn', r2:'warn', no:'fail' };
    let checks = 0;
    const v = (rule_id, severity, L, condition, actual, expected, fields, evidence, pi) => V.push({ rule_id, severity, id: L.id, name: L.name, profile: pi == null ? null : pi, condition, actual, expected, conflicting_fields: fields, evidence });
    const cls = h => /st-fail/.test(h.split('</span>')[0]) ? 'fail' : /st-warn/.test(h.split('</span>')[0]) ? 'warn' : /st-ok/.test(h.split('</span>')[0]) ? 'ok' : '?';
    const real = LISTINGS.filter(L => !L.sample);
    // ---------- 공고 단위 (내 조건과 무관한 사실 ↔ 파생 결과) ----------
    S.profile = Object.assign({}, DEFAULT_PROFILE, profiles[0]); save();
    for (const L of real) {
      const known = { duty: L.residenceDuty == null ? 'UNKNOWN' : L.residenceDuty > 0 ? 'CONFIRMED' : 'NOT_APPLICABLE', cap: L.priceCap == null ? 'UNKNOWN' : L.priceCap ? 'CONFIRMED' : 'NOT_APPLICABLE' };
      stat[L.id] = { name: L.name, unit: L.unit, fixture: !!L._fixture, duty: known.duty, priceCap: known.cap, state: 'NORMAL' };
      // DUTY-001·002: 실거주 의무는 수도권 분양가상한제 주택만 (주택법 제57조의2). 상한제가 아니면 거주의무를 '모름'으로 둘 이유가 없다
      checks += 2;
      if (L.residenceDuty > 0 && !(L.capital && L.priceCap)) v('DUTY-001', 'MEDIUM', L, '거주의무 CONFIRMED', '수도권 분양가상한제 아님', '거주의무는 수도권 분양가상한제 주택만', ['residenceDuty', 'capital', 'priceCap'], '주택법 제57조의2');
      if (L.priceCap === false && L.residenceDuty == null) v('DUTY-002', 'MEDIUM', L, '분양가상한제 NOT_APPLICABLE', '거주의무 UNKNOWN', '거주의무 NOT_APPLICABLE', ['priceCap', 'residenceDuty'], '주택법 제57조의2');
      // RENT-001: 임대(청약홈 RENT_SECD_NM 또는 공고명)는 분양처럼 보이면 안 됨 — 카드에 '공공임대', 금액은 '임대보증금', 시세 차익 없음
      if (L.rental || /임대/.test(L.rentSecd || '')) { checks += 3; const card = document.createElement('div'); card.innerHTML = cardBadges(L) + ' ' + (typeof kindOf === 'function' ? kindOf(L) : '');
        if (!/공공임대/.test(card.textContent)) v('RENT-001', 'CRITICAL', L, '임대 공고', '카드에 공공임대 표시 없음', "'공공임대' 배지", ['rental', 'cardBadges'], '청약홈 RENT_SECD_NM');
        if (L.mktBase != null || L.mktLow != null) v('RENT-001', 'CRITICAL', L, '임대 공고', '시세·마진 계산됨', '시세 차익 없음 (금액은 임대보증금)', ['rental', 'mktBase'], '모집공고문 임대조건');
        if (on('judge_scope') && judgeScope(L).level === 'full') v('RENT-001', 'CRITICAL', L, '임대 공고', '분양 규칙으로 전부 판정(full)', 'partial 또는 none', ['rental', 'judgeScope'], '공고 유형'); }
      if (isRental(L) || !L.price) continue;
      delete S.plan[L.id];
      const jc = jeonseCheck(L), o = planOpt(L), f = funding(L, S.profile, o);
      S.id = L.id; S.view = 'plan'; render();
      const t = txt(), pill = (document.querySelector('.card .row .pill') || {}).textContent || '';
      // LEASE-001: 거주의무 모름 → 전세 결과도 '확인 필요'(또는 불가), '실거주 의무 없음'으로 쓰지 않음
      checks += 5;
      if (L.residenceDuty == null && !['check', 'no'].includes(jc.status)) v('LEASE-001', 'HIGH', L, '거주의무 UNKNOWN', '전세 ' + jc.status, '전세 확인 필요(check)', ['residenceDuty', 'jeonseStatus'], '공고문 단지 주요정보 거주의무기간 미확인');
      if (L.residenceDuty == null && /실거주 의무 없음/.test(t)) v('LEASE-001', 'HIGH', L, '거주의무 UNKNOWN', "화면 '실거주 의무 없음'", "'실거주 의무 확인 필요'", ['residenceDuty', 'chip'], '자금 플랜 지역 규제 칩');
      // LEASE-002: 거주의무 확인 → 전세 '가능' 단정 금지, 기간 표시
      if (L.residenceDuty > 0 && (jc.status === 'ok' || !new RegExp('실거주 의무 ' + L.residenceDuty + '년').test(t))) v('LEASE-002', 'HIGH', L, '거주의무 ' + L.residenceDuty + '년 CONFIRMED', '전세 ' + jc.status + ' · 칩 ' + (/실거주 의무 \d년/.test(t) ? '있음' : '없음'), '전세 조건부 이상 · 실거주 의무 N년 표시', ['residenceDuty', 'jeonseStatus'], '공고문 거주의무기간');
      // LEASE-006: 최초 입주가능일 + 3년(입주 기한)이 잔금 + 2년보다 이르면 '전세 2년'을 그대로 안내하면 안 됨 (2026910236 철산자이: 입주가능일 2025.05.30)
      if (L.residenceDuty > 0 && L.dutyFrom) { checks++; const due = addYears(L.dutyFrom, RULES.dutyDeferralYears), st0 = L.balance && L.balance > TODAY ? L.balance : TODAY;
        if (due < addYears(st0, 2) && jc.reasons.some(r => /전세는 한 번\(2년\)만/.test(r.t))) v('LEASE-006', 'HIGH', L, '입주 기한 ' + due, "'전세 한 번(2년)' 안내", '남은 기간만큼만 전세 가능 또는 불가', ['dutyFrom', 'balance', 'jeonseReasons'], '공고문 최초 입주가능일 · 주택법 제57조의2'); }
      // LEASE-003: 거주의무 없음 확인 → '있을 수 있어요'·'확인하지 못했어요' 같은 모름 문구가 없어야
      if (L.residenceDuty === 0 && /실거주 의무가 (있을 수|있는지)|실거주 의무 확인 필요/.test(t)) v('LEASE-003', 'HIGH', L, '거주의무 NOT_APPLICABLE', '화면이 거주의무를 모른다고 함', '거주의무 없음으로 일관', ['residenceDuty', 'jeonseReasons'], '공고문 거주의무기간 없음');
      // LEASE-004·005: 전세 불가·확인 필요인데 전세를 기본 계획으로 쓰거나 막지 않음
      if (jc.status === 'no' && !/이 단지는 불가/.test(t)) v('LEASE-004', 'CRITICAL', L, '전세 불가', '전세 시나리오 계산이 보임', '전세 시나리오 막음', ['jeonseStatus', 'plan'], '자금 플랜');
      if (['no', 'check'].includes(jc.status) && o.mode === 'jeonse') v('LEASE-005', 'HIGH', L, '전세 ' + jc.status, '기본 계획 = 전세', '기본 계획 = 잔금대출(실거주)', ['jeonseStatus', 'planMode'], '자금 플랜 기본값');
      // FUND-001: 필요 자금 ≥ 분양가 + 확장비 (취득세 별도)
      checks += 4;
      if (f.total + 1e-6 < L.price + (L.ext || 0)) v('FUND-001', 'HIGH', L, '분양가 ' + L.price + '억 + 확장 ' + (L.ext || 0), '필요 자금 ' + f.total, '필요 자금 ≥ 분양가 + 확장비', ['price', 'ext', 'fundingTotal'], '자금 플랜 계산');
      // FUND-002: 외부 조달 = 필요 자금 − 내 자금
      const tiles = [...document.querySelectorAll('.tiles .tile .v')].map(x => x.textContent);
      if (tiles.length >= 3 && tiles[2] !== fmt(Math.max(0, f.total - f.available))) v('FUND-002', 'HIGH', L, '필요 ' + tiles[0] + ' · 내 ' + tiles[1], '외부 조달 ' + tiles[2], fmt(Math.max(0, f.total - f.available)), ['fundingTotal', 'available', 'external'], '자금 플랜 타일');
      // FUND-003: 시나리오 '가능' ⇒ 부족분 0 이하이고 막히지 않음, 거주의무 모름이면 '확인 필요'
      document.querySelectorAll('.scen').forEach(sc => { const p = (sc.querySelector('.pill') || {}).textContent || '', gapTxt = sc.innerText;
        if (p === '가능' && /부족분/.test(gapTxt)) v('FUND-003', 'CRITICAL', L, '시나리오 부족분 있음', "'가능'", "'N억 부족'", ['gap', 'scenarioPill'], '자금 플랜 시나리오'); });
      if (jc.status === 'check' && [...document.querySelectorAll('.scen')].some(sc => /전세/.test((sc.querySelector('h2') || {}).textContent || '') && ((sc.querySelector('.pill') || {}).textContent === '가능'))) v('FUND-004', 'HIGH', L, '거주의무 UNKNOWN', "전세 시나리오 '가능'", "전세 시나리오 '확인 필요'", ['residenceDuty', 'scenarioPill'], '자금 플랜 시나리오');
      // FUND-006 (2026-10-07 사용자 제보 'LTV 70%인데 대출 0원'): 시세가 없어도 집값 기준(LTV) 대출이 0원이면 안 됨, 전세 시세가 없으면 0원으로 계산하지 않고 '입력 필요'
      checks += 2;
      if (L.price > 0 && !(f.loanLtv > 0)) v('FUND-006', 'CRITICAL', L, '시세 ' + (L.mktBase == null ? '없음' : L.mktBase), 'LTV 대출 ' + f.loanLtv, '시세 없으면 분양가 기준 LTV', ['mktBase', 'loanLtv'], '자금 플랜 잔금대출');
      if (f.jeonseUnk && [...document.querySelectorAll('.scen')].some(sc => /전세/.test((sc.querySelector('h2') || {}).textContent || '') && (/부족분|여유분/.test(sc.innerText) || !/입력 필요|불가/.test((sc.querySelector('.pill') || {}).textContent || '')))) v('FUND-006', 'HIGH', L, '전세 시세 없음', '전세 0원으로 계산', "'전세 보증금 입력 필요'", ['jeonse', 'scenarioPill'], '자금 플랜 전세 시나리오');
      if (L.residenceDuty == null || L.priceCap == null) stat[L.id].state = 'UNKNOWN';
      else if (jc.status !== 'ok') stat[L.id].state = 'WARNING';
    }
    // ---------- 내 조건 × 공고 (자격·자금·화면 문구) ----------
    profiles.forEach((pr, pi) => {
      S.profile = Object.assign({}, DEFAULT_PROFILE, pr); save(); S.plan = {};
      const owns = pr.selfOwn === true || pr.hhHomes === '1' || pr.hhHomes === '2+';
      for (const L of real) {
        const bucket = eligBucket(L, S.profile), card = meLine(L), cc = cls(card), e = eligibility(L, S.profile);
        checks += 6;
        // ELIG-001: 공공(국민주택)은 1·2순위 모두 무주택세대구성원 → 유주택이면 '가능' 금지 (주택공급에 관한 규칙 제27조)
        if (owns && L.houseDtl === '국민' && !isRental(L) && bucket === 'ok') v('ELIG-001', 'CRITICAL', L, '유주택 · 국민주택', '판정 가능', '불가(또는 확인 필요)', ['owns', 'houseDtl', 'bucket'], '주택공급에 관한 규칙 제27조', pi);
        // ELIG-002: 공통 조건(거주지·재당첨) 불가 → 어떤 공급으로도 '가능' 금지
        const common = e.items.filter(i => (i.k === '거주지' || i.k === '재당첨 제한 (내 이력)') && i.s === 'fail');
        if (common.length && bucket === 'ok') v('ELIG-002', 'CRITICAL', L, common.map(i => i.k).join('·') + ' 불가', '판정 가능', '불가', ['commonCondition', 'bucket'], '공고문 신청자격', pi);
        // UI-001: 카드 결론 = 판정 묶음 (같은 사실을 다르게 말하지 않음)
        if (cc !== B[bucket]) v('UI-001', 'HIGH', L, '판정 ' + bucket, '카드 ' + cc, B[bucket], ['meLine', 'eligBucket'], '목록 카드', pi);
        // SCOPE-001: 판정 범위 밖(임대인데 자격표 못 읽음 등) → '가능'·'불가'로 확정 금지 (2026-10-02 사용자 QA '임대 → 분양', '지원하지 않는 유형 → 가능')
        const sc = judgeScope(L); checks++;
        if (sc.level === 'none' && bucket !== 'unsure') v('SCOPE-001', 'CRITICAL', L, '판정 범위 밖: ' + sc.why.slice(0, 30), '판정 ' + bucket, '확인 필요', ['judgeScope', 'bucket'], '공고 유형', pi);
        if (sc.level === 'none' && spTypesFor(L).some(t => spJudge(L, S.profile, t).s !== 'warn')) v('SCOPE-001', 'CRITICAL', L, '판정 범위 밖', '특별공급 가능/불가 확정', '확인 필요', ['judgeScope', 'spResult'], '공고 유형', pi);
        // FUND-005: 카드 '자금 가능'인데 계획 기준 부족분 > 0
        if (/자금 가능/.test(card)) { const o = planOpt(L), f = funding(L, S.profile, o); if (bestGap(f, o) > 1e-9) v('FUND-005', 'CRITICAL', L, '부족분 ' + fmt(bestGap(f, o)), "카드 '자금 가능'", "카드 '자금 N 부족'", ['gap', 'meLine'], '목록 카드', pi);
          if (o.mode === 'jeonse' && ['no', 'check'].includes(jeonseCheck(L).status)) v('FUND-006', 'HIGH', L, '전세 ' + jeonseCheck(L).status, "카드 '자금 가능'(전세 계획)", '전세 없이 계산', ['jeonseStatus', 'meLine'], '목록 카드', pi); }
        // ELIG-003·004: 특별공급 '가능'인데 소득·자산이 그 유형 최대 기준(출산 완화 +20%p 포함)을 넘음
        for (const t of spTypesFor(L)) { const r = spJudge(L, S.profile, t); if (r.s !== 'ok') continue; checks += 2;
          const R = SP_RULES[r.pub ? 'public' : 'minyoung'][t], n = r.hhN || S.profile.hhSize, inc = spIncome(S.profile);
          if (r.rsRows) { const top = r.rsRows[r.rsRows.length - 1]; if (inc.monthly > top[3] / top[2] * (top[2] + 20) + 1) v('ELIG-003', 'CRITICAL', L, t + ' 소득 월 ' + Math.round(inc.monthly), '특공 가능', '불가', ['income', 'spResult'], '공고문 <표4>', pi); }
          else if (r.pub && R.max && n && inc.monthly > spAmt(n, R.max[inc.dual ? 1 : 0] + 20) + 1) v('ELIG-003', 'CRITICAL', L, t + ' 소득 ' + Math.round(inc.monthly / spBase(n) * 100) + '%', '특공 가능', '불가 (상한 ' + R.max[inc.dual ? 1 : 0] + '%+20%p 초과)', ['income', 'spResult'], '공고문 소득 기준표', pi);
          if (r.pub && !r.rsRows && (S.profile.realEstate || 0) > 25860) v('ELIG-004', 'CRITICAL', L, t + ' 부동산 ' + S.profile.realEstate + '만', '특공 가능', '불가 (출산 완화 최대 2억5,860만 초과)', ['realEstate', 'spResult'], '공고문 <표3>', pi);
          if (r.rsRows && townAssetParts(S.profile).total > 43100) v('ELIG-004', 'CRITICAL', L, t + ' 총자산 ' + townAssetParts(S.profile).total + '만', '특공 가능', '불가', ['totalAsset', 'spResult'], '공고문 <표2>·<표3>', pi); }
      }
    });
    // ---------- 상세 화면 안 문구 (한 화면이 서로 반대로 말하는지) — 조건 6개만 (느림) ----------
    profiles.filter((_, i) => i % 7 === 0).forEach((pr, pi) => {
      S.profile = Object.assign({}, DEFAULT_PROFILE, pr); save(); S.plan = {};
      for (const L of real) { S.id = L.id; S.view = 'detail'; render(); checks += 2;
        const h = document.querySelector('.rhero'), tone = h ? (h.className.match(/t-(ok|warn|fail|info)/) || [])[1] : null, t = txt();
        if (tone === 'fail' && /자격과 자금 모두 가능|일반공급은 자격과 자금 모두 가능/.test(t)) v('UI-002', 'HIGH', L, "맨 위 '신청 불가'", "같은 화면 '자격과 자금 모두 가능'", '한 결론', ['rhero', 'mineNote'], '공고 상세', pi * 7);
        if (tone === 'ok' && /지금 조건으로는 신청 불가/.test(t)) v('UI-002', 'HIGH', L, "맨 위 '가능'", "같은 화면 '지금 조건으로는 신청 불가'", '한 결론', ['rhero', 'checklist'], '공고 상세', pi * 7);
        // STATUS-001: 마감 공고는 상세에서도 마감을 알려야 (신청 가능처럼 보이면 안 됨)
        if (statusOf(L) === '마감' && !/마감/.test(t)) v('STATUS-001', 'CRITICAL', L, '접수 마감 ' + (L.applyEnd || L.apply), '상세에 마감 표시 없음', "'마감' 표시", ['applyEnd', 'detail'], '청약홈 일정', pi * 7); }
    });
    // ---------- LH 임대 (기능 lh_rental, 2026-10-05): 공고문 조건(terms) ↔ 계층별 판정 ↔ 목록 카드 ----------
    const lhNotices = (RENTAL && RENTAL.notices || []).filter(N => N.terms && N.terms.groups && N.terms.groups.length);
    const ORDR = { ok: 0, check: 1, no: 2, na: 3 };
    for (const pr0 of lhProfiles.concat(profiles)) {
      const p = Object.assign({}, DEFAULT_PROFILE, pr0);
      for (const N of lhNotices) {
        const J = rentalJudge(N, p), T = N.terms, ref = N.posted, age = rAge(p.birth, ref), L = { id: 'LH-' + N.id, name: N.name };
        J.groups.forEach((g, gi) => { const G = T.groups[gi]; checks += 6; if (g.s !== 'ok') return;
          // LH-ELIG-001: 가능인데 소득이 그 계층 최대 기준(1인·2인 가산 + 맞벌이(30%p 또는 공고문 dual_add) + 출산 20%p)을 넘음
          if (G.income_pct && G.income_pct !== 'excluded' && p.hhIncomeYear != null && p.hhIncomeYear !== '' && p.hhSize && !(G.key === '청년' && p.household === 'parents') && G.key !== '대학생') {
            const n = Number(p.hhSize), pct = G.income_pct[n === 1 ? '1' : n === 2 ? '2' : '3+'], base = rIncomeBase(N, n);
            if (pct != null && base && Number(p.hhIncomeYear) * 10000 / 12 > base * (pct + 20 + Math.max(30, Number(G.dual_add) || 0)) / 100 + 1)   /* 맞벌이 가산은 공고문 값(SH 신혼·신생아 Ⅱ +70%p)이 30%p 보다 크면 그 값 */ v('LH-ELIG-001', 'CRITICAL', L, G.key + ' 소득 월 ' + Math.round(Number(p.hhIncomeYear) * 10000 / 12), '계층 가능', '불가', ['hhIncomeYear', 'terms.income_pct'], '공고문 소득 기준표', null);
          }
          // LH-ELIG-002: 가능인데 자동차·총자산이 한도(+출산 20%)를 넘음
          if (typeof G.car_manwon === 'number' && p.carValue != null && p.carValue !== '' && Number(p.carValue) > G.car_manwon * 1.2 + 1) v('LH-ELIG-002', 'CRITICAL', L, G.key + ' 자동차 ' + p.carValue, '계층 가능', '불가', ['carValue', 'terms.car_manwon'], '공고문 자산 기준', null);
          if (typeof G.car_manwon === 'number' && G.car_manwon === 0 && Number(p.carValue) > 0) v('LH-ELIG-002', 'CRITICAL', L, G.key + ' 자동차 소유', '계층 가능', '불가(자동차 소유 불가)', ['carValue'], '공고문 대학생 계층', null);
          if (typeof G.asset_manwon === 'number' && !['대학생'].includes(G.key) && !(G.key === '청년' && p.household === 'parents') && p.realEstate != null && p.carValue != null && townAssetParts(p).total > G.asset_manwon * 1.2 + 1) v('LH-ELIG-002', 'CRITICAL', L, G.key + ' 총자산 ' + townAssetParts(p).total, '계층 가능', '불가', ['totalAsset', 'terms.asset_manwon'], '공고문 자산 기준', null);
          // LH-ELIG-003: 신청자격 거주 요건 밖인데 가능
          if (T.local && T.local.sido && p.homeSido && p.homeSido !== T.local.sido) v('LH-ELIG-003', 'CRITICAL', L, G.key + ' 거주 ' + p.homeSido, '계층 가능', '불가(' + T.local.name + ' 거주자만)', ['homeSido', 'terms.local'], '공고문 신청자격', null);
          // 사는 시·군 자유 입력('경남 창원시 마산회원구' 등)에서 시·군 낱말을 찾아 비교 — 시·군 낱말이 없으면(구만) 가능이면 안 됨
          const sgw = !(T.local && T.local.sigun) ? [] : String(p.homeSigun || '').split(/[\s,·]+/).filter(w => /(시|군)$/.test(w) && !/(특별시|광역시|특별자치시)$/.test(w)).map(w => w.replace(/(시|군)$/, ''));
          const sgOne = !!(T.local && T.local.sigun) && String(p.homeSigun || '').trim().split(/\s+/).length === 1 && String(p.homeSigun).trim().replace(/(시|군)$/, '') === bareArea(T.local.sigun);
          if (T.local && T.local.sigun && p.homeSigun && !sgw.includes(bareArea(T.local.sigun)) && !sgOne) v('LH-ELIG-003', 'CRITICAL', L, G.key + ' 거주 ' + p.homeSigun, '계층 가능', '불가(' + T.local.name + ' 거주자만)', ['homeSigun', 'terms.local'], '공고문 신청자격', null);
          if (Array.isArray(T.regions) && T.regions.length && p.homeSido && !T.regions.includes(p.homeSido)) v('LH-ELIG-003', 'CRITICAL', L, G.key + ' 거주 ' + p.homeSido, '계층 가능', '불가', ['homeSido', 'terms.regions'], '공고문 신청자격', null);
          // LH-ELIG-004: 나이 범위 밖인데 가능 (청년·고령자), 미성년인데 가능(대학생·청년 외)
          if (age != null && G.key === '청년' && !G.married_ok && (age < (G.age_min || 19) || age > (G.age_max || 39))) v('LH-ELIG-004', 'CRITICAL', L, '청년 나이 ' + age, '가능', '해당 없음', ['birth'], '공고문 청년 계층', null);
          if (age != null && G.key === '고령자' && age < 65) v('LH-ELIG-004', 'CRITICAL', L, '고령자 나이 ' + age, '가능', '해당 없음', ['birth'], '공고문 고령자 계층', null);
          if (age != null && age < 19 && !['대학생', '청년'].includes(G.key) && !(p.household === 'head' && p.lhMinorHead === true)) v('LH-ELIG-004', 'CRITICAL', L, '미성년 ' + age, '가능', '불가(성년자)', ['birth'], '공고문 신청자격', null);
          // LH-HOME-001: 무주택 완화 없는 공고에서 집이 있는데 가능
          const own = G.homeless === 'self' ? p.selfOwn === true : (p.selfOwn === true || (p.married === true && p.spouseOwn === true));
          if (own && !T.homeless_relaxed) v('LH-HOME-001', 'CRITICAL', L, G.key + ' 주택 소유', '가능', '불가', ['selfOwn', 'spouseOwn'], '공고문 무주택 요건', null);
          // LH-MONO-001: 모르는 칸이 있는데 가능 (그 기준이 적용되는 경우)
          const unk = [];
          if (G.income_pct && G.income_pct !== 'excluded' && G.key !== '대학생' && (p.hhSize == null || p.hhSize === '')) unk.push('hhSize');
          if (typeof G.car_manwon === 'number' && (p.carValue == null || p.carValue === '')) unk.push('carValue');
          if ((G.key === '청년' || G.key === '고령자') && !p.birth) unk.push('birth');
          // 2026-10-05 R3~R5: 기본값 0·false 칸은 '입력함'(_set) 표시가 있어야 값으로 본다
          const ent = k => p[k] != null && p[k] !== '' && !((DEFAULT_PROFILE[k] === 0 || DEFAULT_PROFILE[k] === false) && p[k] === DEFAULT_PROFILE[k] && !(p._set || []).includes(k));
          const ymember = G.key === '청년' && p.household === 'parents' && !G.married_ok;
          if (G.income_pct && G.income_pct !== 'excluded' && !['대학생', '주거급여수급자'].includes(G.key) && (ymember ? !ent('income') : (p.hhIncomeYear == null || p.hhIncomeYear === '') && !ent('income'))) unk.push('income');
          if (typeof G.asset_manwon === 'number' && !['대학생', '주거급여수급자'].includes(G.key) && !ymember && ['realEstate', 'carValue', 'cash', 'liquid', 'deposit'].some(k => !ent(k))) unk.push('asset');
          if (G.homeless === 'household' && !T.homeless_relaxed && p.hhHomes !== '0' && !(Number(p.hhSize) === 1 && p.married === false && p.selfOwn === false && !(p.eldersOnDeed > 0) && p.household !== 'parents')) unk.push('hhHomes');
          if (!['대학생', '청년'].includes(G.key) && !p.birth) unk.push('birth(성년)');
          if (unk.length) v('LH-MONO-001', 'CRITICAL', L, G.key + ' 모름 ' + unk.join(','), '가능', '확인 필요', unk, '불확실성 전파', null);
        });
        // LH-UI-001: 공고 결론 = 계층 중 가장 좋은 결론 (대학생·주거급여만 있는 공고 제외)
        checks++;
        const main = J.groups.filter(g => !['대학생', '주거급여수급자'].includes(g.key));
        if (main.length && J.s !== main.slice().sort((a, b) => ORDR[a.s] - ORDR[b.s])[0].s) v('LH-UI-001', 'HIGH', L, '계층 ' + main.map(g => g.s).join(','), '공고 결론 ' + J.s, '가장 좋은 계층 결론', ['rentalJudge'], '화면', null);
      }
    }
    V.forEach(x => { if (stat[x.id] && x.severity !== 'MEDIUM') stat[x.id].state = 'CONFLICT'; });
    return { checks, V, stat, nListings: real.length, nProfiles: profiles.length };
  }, [profiles, fx, lhProfiles]);
  await b.close();
  const sev = { CRITICAL: 0, HIGH: 0, MEDIUM: 0 }, rules = {};
  out.V.forEach(x => { sev[x.severity]++; rules[x.rule_id] = (rules[x.rule_id] || 0) + 1; });
  const states = {}; Object.values(out.stat).forEach(s => { states[s.state] = (states[s.state] || 0) + 1; });
  const uniq = [...new Map(out.V.map(x => [x.rule_id + x.id + x.actual, x])).values()];
  writeFileSync(join(ROOT, 'evidence/qa/cross-rule.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), listings: out.nListings, profiles: out.nProfiles, checks: out.checks,
    conflicts: out.V.length, severity: sev, rules, states, examples: uniq.slice(0, 60), unknown: Object.entries(out.stat).filter(([, s]) => s.state === 'UNKNOWN').map(([id, s]) => ({ id, name: s.name, duty: s.duty, priceCap: s.priceCap })).slice(0, 40), pageErrors: errs.slice(0, 5) }, null, 1) + '\n');
  console.log(`[QA 교차 규칙] 공고 ${out.nListings}개 × 조건 ${out.nProfiles}개 · 검사 ${out.checks}회 · 충돌 ${out.V.length}건 (CRITICAL ${sev.CRITICAL} · HIGH ${sev.HIGH} · MEDIUM ${sev.MEDIUM}) · 공고 상태 ${Object.entries(states).map(([k, n]) => k + ' ' + n).join(' · ')}${errs.length ? ' · 화면 오류 ' + errs.length : ''}`);
  Object.entries(rules).forEach(([k, n]) => console.log('  ' + k + ': ' + n));
  uniq.slice(0, 12).forEach(x => console.log('  ', x.rule_id, x.severity, x.id, (x.name || '').slice(0, 14), '|', x.condition, '→', x.actual, '(기대:', x.expected + ')'));
  process.exit(sev.CRITICAL || sev.HIGH || errs.length ? 1 : 0);
})();
