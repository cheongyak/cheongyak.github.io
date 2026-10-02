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
  const out = await page.evaluate(([profiles, fx]) => {
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
    V.forEach(x => { if (stat[x.id] && x.severity !== 'MEDIUM') stat[x.id].state = 'CONFLICT'; });
    return { checks, V, stat, nListings: real.length, nProfiles: profiles.length };
  }, [profiles, fx]);
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
