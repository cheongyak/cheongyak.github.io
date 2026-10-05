// LH 임대 블라인드 감사 사례 만들기 (기능 lh_rental): 무작위 내 조건 × 지금 LH 임대 공고 → cases.json(검토자용, 프로필만) + app.json(앱 판정, 검토자에게 주지 않음)
// 사용: NODE_PATH=$(npm root -g) node tools/qa/audit/audit_gen_lh.cjs <출력폴더> [40] [시드] [sparse]
// sparse(3차 감사, 2026-10-05 R3~R5): 칸 몇 개를 '모름'(null)으로 비운 사례 — 앱에는 기본값 0·false 칸을 '입력 안 함'(_set 없음)으로, 검토자에게는 null 로 준다. 대표 공고(818·740·581·806·870·855·765·742)를 자주 고른다  · 지시서 tools/qa/audit/brief_lh.md · 비교 audit_cmp_lh.py
const { chromium } = require('playwright');
const { readFileSync, existsSync, writeFileSync, mkdirSync } = require('node:fs'); const { join, extname } = require('node:path');
const dir = process.cwd() + '/docs', OUT = process.argv[2], N = +process.argv[3] || 40, SEED = +process.argv[4] || 20261005, SPARSE = process.argv[5] === 'sparse';
(async () => {
  mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }); const p = await b.newPage();
  await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.abort();
    const f = join(dir, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: readFileSync(f), contentType: extname(f)==='.html'?'text/html':'application/json' }); });
  await p.goto('http://site.local/', { waitUntil: 'networkidle' });
  await p.evaluate(() => new Promise(res => { loadRental(); const t = setInterval(() => { if (RENTAL) { clearInterval(t); res(); } }, 50); }));
  const res = await p.evaluate(([N, SEED, SPARSE]) => {
    let s = SEED; const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648;
    const pick = a => a[Math.floor(rnd() * a.length)], int = (a, b) => a + Math.floor(rnd() * (b - a + 1));
    const day = (y0, y1) => `${int(y0, y1)}-${String(int(1, 12)).padStart(2, '0')}-${String(int(1, 28)).padStart(2, '0')}`;
    const SIGUN = { '부산':['해운대구','사하구'], '경남':['창원시','김해시','남해군'], '전북':['전주시','익산시','군산시','남원시'], '경기':['양주시','수원시'], '강원':['원주시','태백시'], '서울':['마포구'], '대구':['수성구'], '충남':['아산시'], '경북':['고령군'], '인천':['남동구'] };
    const NS = RENTAL.notices.filter(N => N.terms && N.terms.groups && N.terms.groups.length);
    const yn = () => pick([true, false, null, null]);
    const cases = [], app = [];
    for (let i = 0; i < N; i++) {
      const REP = NS.filter(x => /(818|740|581|806|870|855|765|742)$/.test(x.id));
      const N0 = SPARSE && REP.length && rnd() < 0.7 ? pick(REP) : pick(NS), sido = pick(Object.keys(SIGUN)), married = rnd() < 0.45, kids = married ? pick([0, 1, 2]) : pick([0, 0, 0, 1]);
      const pr = { birth: pick([day(1950, 1960), day(1962, 1985), day(1986, 2007), day(1986, 2007), day(2004, 2008)]), married: rnd() < 0.08 ? null : married,
        marriedOn: married ? day(2012, 2025) : '', household: married ? 'head' : pick(['head', 'head', 'parents']), selfOwn: rnd() < 0.15, spouseOwn: married && rnd() < 0.1, eldersOnDeed: pick([0, 0, 0, 1]), parentsOwn: rnd() < 0.4,
        kidsMinor: kids, youngestBirth: kids ? pick([day(2015, 2022), day(2023, 2026)]) : '', pregnant: rnd() < 0.05, hhSize: (married ? 2 : 1) + kids + (rnd() < 0.1 ? 2 : 0),
        income: pick([0, 1800, 2400, 3600, 4800, 6000]), spouseIncome: married ? pick([0, 0, 2400, 4000]) : 0,
        realEstate: pick([0, 0, 0, 10000, 22000, 40000]), carValue: pick([0, 0, 1500, 3000, 4542, 5000]), cash: pick([500, 3000, 10000]), liquid: 0, deposit: pick([0, 3000]),
        townInsurance: 0, townFinOther: 0, townOtherAsset: 0, townDebt: pick([0, 0, 5000]), youthAsset: pick([500, 3000, 12000, 26000]),
        homeSido: sido, homeSigun: pick(SIGUN[sido]), acctType: pick(['all', 'all', 'all', 'none', 'deposit']), acctSince: day(2010, 2026), acctCount: pick([0, 5, 12, 60]),
        lhStudent: yn(), lhStudentIncome: yn(), lhHousingBenefit: yn(), lhSingleParent: yn(), lhHomeOutside: yn(), lhStartupRec: yn(), lhJobCriteria: yn(), lhLongWorker: yn(), lhBirthKids: pick([null, 0, 1]) };
      pr.hhIncomeYear = rnd() < 0.1 ? null : pr.income + pr.spouseIncome;
      if (!married) pr.spouseOwn = false;
      if (pr.household !== 'parents' && !pr.eldersOnDeed) pr.parentsOwn = null;   // 같은 등본에 부모님이 없으면 묻지 않는 칸 (2026-10-05 감사: 어긋난 프로필 L24·L29)
      if (married && pr.birth > '2005-01-01') pr.birth = '1990-05-01';           // 혼인 중 미성년 같은 어긋난 프로필 방지 (L18)
      pr.hhHomes = pr.selfOwn || pr.spouseOwn || pr.parentsOwn === true ? pick(['1', '1', '2+']) : '0';
      if (SPARSE) pr.lhPreWed = !married ? pick([true, false, null]) : null;
      const appP = Object.assign({}, DEFAULT_PROFILE, pr);
      if (SPARSE) {   // 2~5칸을 모름으로
        const DROP = ['income', 'spouseIncome', 'hhIncomeYear', 'cash', 'liquid', 'deposit', 'realEstate', 'carValue', 'selfOwn', 'spouseOwn', 'hhHomes', 'hhSize', 'birth', 'married', 'kidsMinor', 'youngestBirth', 'pregnant', 'homeSido', 'homeSigun', 'acctType', 'townDebt', 'youthAsset', 'parentsOwn'];
        const drop = new Set(); const nd = int(2, 5); while (drop.size < nd) drop.add(pick(DROP));
        drop.forEach(k => { pr[k] = null; appP[k] = ZERO_KEYS.includes(k) ? DEFAULT_PROFILE[k] : (typeof DEFAULT_PROFILE[k] === 'string' ? '' : null); });
        appP._set = ZERO_KEYS.filter(k => !drop.has(k));
        pr._unknown = [...drop];
      } else appP._set = ZERO_KEYS.slice();
      const P = appP, J = rentalJudge(N0, P);
      const id = 'L' + String(i + 1).padStart(2, '0');
      cases.push({ id, notice_id: N0.id, type: N0.type, name: N0.name, notice_date: N0.posted, region: N0.region, profile: pr });
      app.push({ id, groups: J.groups.map(g => ({ group: g.key, s: g.s, items: g.items.map(x => x.s + ':' + x.t) })) });
    }
    return { cases, app };
  }, [N, SEED, SPARSE]);
  writeFileSync(OUT + '/cases.json', JSON.stringify(res.cases, null, 1)); writeFileSync(OUT + '/app.json', JSON.stringify(res.app, null, 1));
  console.log(res.cases.length, 'cases', [...new Set(res.cases.map(c => c.notice_id))].length, 'notices');
  await b.close();
})();
