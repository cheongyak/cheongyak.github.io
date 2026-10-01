const { chromium } = require('playwright');
const { readFileSync, existsSync, writeFileSync } = require('node:fs'); const { join, extname } = require('node:path');
const dir = process.cwd() + '/docs', OUT = process.argv[2], N = +process.argv[3] || 40, SEED = +process.argv[4] || 20261001;
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }); const p = await b.newPage();
  await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.abort();
    const f = join(dir, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: readFileSync(f), contentType: extname(f)==='.html'?'text/html':'application/json' }); });
  await p.goto('http://site.local/', { waitUntil: 'networkidle' }); await p.waitForTimeout(600);
  const res = await p.evaluate(([N, SEED]) => {
    let s = SEED; const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648;
    const pick = a => a[Math.floor(rnd() * a.length)], int = (a, b) => a + Math.floor(rnd() * (b - a + 1));
    const day = (y0, y1) => `${int(y0, y1)}-${String(int(1, 12)).padStart(2, '0')}-${String(int(1, 28)).padStart(2, '0')}`;
    const SIDO = { '서울':['강남구','노원구','마포구'], '경기':['광명시','성남시','양주시','의정부시','하남시','화성시'], '인천':['계양구','서구','연수구'], '부산':['강서구','해운대구'], '대구':['수성구'], '충남':['천안시'] };
    const lst = LISTINGS.filter(L => !L.sample && L.category === 'general');
    const cases = [], app = [];
    for (let i = 0; i < N; i++) {
      const L = pick(lst), sido = rnd() < 0.55 ? L.sido : pick(Object.keys(SIDO)), sigun = rnd() < 0.5 && sido === L.sido && L.sigungu ? L.sigungu : pick(SIDO[sido] || ['기타']);
      const married = rnd() < 0.6, kids = married ? pick([0, 0, 1, 1, 2, 3]) : 0, newborn = kids > 0 && rnd() < 0.4, owns = rnd() < 0.2, birth = day(1965, 2001);
      const pr = { homeSido: sido, homeSigun: sigun, sidoOwnSince: day(2005, 2026).replace(/-\d\d$/, '-01'), household: pick(['head','head','head','parents','spouse']),
        selfOwn: owns, married, marriedOn: married ? day(2012, 2025) : '', spouseOwn: false, acctType: pick(['all','all','all','deposit','']),
        acctSince: day(2008, 2025), acctAmount: pick([200, 300, 600, 1000, 1500]), acctCount: int(3, 150), acctPaid: pick([300, 800, 1500, 3000]),
        hhHomes: owns ? pick(['1','2+']) : pick(['0','0','0','1']), win5y: rnd() < 0.1, everWin: 'no', recentWin: false, birth,
        dependents: married ? Math.min(6, 1 + kids + (rnd() < 0.15 ? 1 : 0)) : (rnd() < 0.1 ? 1 : 0), kidsMinor: kids, youngestBirth: kids ? (newborn ? day(2023, 2026) : day(2010, 2022)) : '',
        pregnant: rnd() < 0.08, hhSize: (married ? 2 : 1) + kids, kidsOnDeed: kids, eldersOnDeed: 0, income: pick([2400, 3600, 4800, 6000, 8000, 11000]),
        spouseIncome: married ? pick([0, 0, 3000, 5000]) : 0, realEstate: pick([0, 0, 0, 10000, 22000, 40000]), carValue: pick([0, 1500, 3000, 5000]),
        hhNeverOwned: !owns && rnd() < 0.7, taxYears5: rnd() < 0.7, elder65: rnd() < 0.1, cash: pick([3000, 10000, 30000]) };
      if (pr.household === 'head') pr.headSince = day(2010, 2025);
      pr.areaSince = pr.sidoOwnSince; pr.sidoSince = pr.sidoOwnSince;
      pr.hhIncomeYear = pr.income + pr.spouseIncome;
      if (pr.acctType === '') { delete pr.acctSince; pr.acctAmount = 0; }
      const P = Object.assign({}, DEFAULT_PROFILE, pr); syncHome(P);
      const e = eligibility(L, P), sc = myScore(L, P), sps = spTypesFor(L);
      const spT = sps.length ? pick(sps) : null, sp = spT ? spJudge(L, P, spT) : null;
      const id = 'A' + String(i + 1).padStart(2, '0');
      cases.push({ id, listing: L.id, notice_id: L.id.split('-')[0], name: L.name, house_type: L.unit || L.id.split('-')[1], area_m2: L.area, kind: L.houseDtl === '국민' ? '공공(국민)' : '민영',
        notice_date: L.notice, sp_type: spT, profile: P });
      app.push({ id, verdict: e.ok ? (e.unsure ? 'unsure' : 'ok') : e.rank2 ? 'rank2' : 'no', items: e.items.map(x => [x.k, x.s, x.v]), score: sc.total,
        sp: sp ? { type: spT, s: sp.s, stage: sp.stage && sp.stage[0], fail: sp.fail, warn: sp.warn } : null });
    }
    return { cases, app };
  }, [N, SEED]);
  writeFileSync(OUT + '/cases.json', JSON.stringify(res.cases, null, 1)); writeFileSync(OUT + '/app.json', JSON.stringify(res.app, null, 1));
  console.log(res.cases.length, [...new Set(res.cases.map(c => c.notice_id))].length, 'notices');
  await b.close();
})();
