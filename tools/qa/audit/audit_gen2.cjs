const { chromium } = require('playwright');
const { readFileSync, existsSync, writeFileSync } = require('node:fs'); const { join, extname } = require('node:path');
// audit_gen2: 층별 추출(민영 규제/비규제·수도권/지방, 공공분양, 신혼희망타운, 무순위)과 서로 어긋나지 않는 프로필 (2026-10-01 판정엔진 감사)
const dir = process.cwd() + '/docs', OUT = process.argv[2], N = +process.argv[3] || 160, SEED = +process.argv[4] || 20261002;
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
    const all = LISTINGS.filter(L => !L.sample);
    const STRATA = [
      ['민영·규제', L => L.category === 'general' && L.houseDtl !== '국민' && L.regulated, 0.24],
      ['민영·비규제·수도권', L => L.category === 'general' && L.houseDtl !== '국민' && !L.regulated && L.capital, 0.16],
      ['민영·비규제·지방', L => L.category === 'general' && L.houseDtl !== '국민' && !L.regulated && !L.capital, 0.18],
      ['공공분양', L => L.category === 'general' && L.houseDtl === '국민' && !isNewlywedTown(L), 0.2],
      ['신혼희망타운', L => L.category === 'general' && isNewlywedTown(L), 0.1],
      ['무순위·재공급', L => L.category === 'remainder', 0.12]];
    const pools = STRATA.map(([n, f, w]) => [n, all.filter(f), w]).filter(x => x[1].length);
    const pickStratum = () => { let r = rnd() * pools.reduce((a, x) => a + x[2], 0); for (const x of pools) { if ((r -= x[2]) <= 0) return x; } return pools[0]; };
    const cases = [], app = [];
    for (let i = 0; i < N; i++) {
      const st = pickStratum(), L = pick(st[1]), sido = rnd() < 0.55 ? L.sido : pick(Object.keys(SIDO)), sigun = rnd() < 0.5 && sido === L.sido && L.sigungu ? L.sigungu : pick(SIDO[sido] || ['기타']);
      const married = rnd() < 0.6, kids = married ? pick([0, 0, 1, 1, 2, 3]) : 0, newborn = kids > 0 && rnd() < 0.4, owns = rnd() < 0.2, birth = day(1965, 2001);
      const pr = { homeSido: sido, homeSigun: sigun, sidoOwnSince: day(2005, 2026).replace(/-\d\d$/, '-01'), household: pick(['head','head','head','parents','spouse']),
        selfOwn: owns, married, marriedOn: married ? day(2012, 2025) : '', spouseOwn: false, acctType: pick(['all','all','all','deposit','']),
        acctSince: day(2008, 2025), acctAmount: pick([200, 300, 600, 1000, 1500]), acctCount: int(3, 150), acctPaid: pick([300, 800, 1500, 3000]),
        hhHomes: owns ? pick(['1','2+']) : pick(['0','0','0','0','1']), win5y: rnd() < 0.1, everWin: 'no', recentWin: false, birth,
        dependents: married ? Math.min(6, 1 + kids + (rnd() < 0.15 ? 1 : 0)) : (rnd() < 0.1 ? 1 : 0), kidsMinor: kids, youngestBirth: kids ? (newborn ? day(2023, 2026) : day(2010, 2022)) : '',
        pregnant: rnd() < 0.08, hhSize: (married ? 2 : 1) + kids, kidsOnDeed: kids, eldersOnDeed: 0, income: pick([2400, 3600, 4800, 6000, 8000, 11000]),
        spouseIncome: married ? pick([0, 0, 3000, 5000]) : 0, realEstate: pick([0, 0, 0, 10000, 22000, 40000]), carValue: pick([0, 1500, 3000, 5000]),
        hhNeverOwned: !owns && rnd() < 0.7, taxYears5: rnd() < 0.7, elder65: rnd() < 0.1, cash: pick([3000, 10000, 30000]) };
      if (pr.household === 'head') pr.headSince = day(2010, 2025);
      // 서로 어긋나지 않게: 세대 주택 1채 이상인데 본인 명의가 아니면 누구 명의인지 정한다, 주택이 있으면 '세대원 모두 주택 이력 없음'은 거짓
      if (pr.hhHomes !== '0' && !owns) pr.hhOwner = pick(['parent60', 'other']);
      if (pr.hhHomes !== '0') pr.hhNeverOwned = false;
      if (pr.household === 'parents') { pr.parents60 = rnd() < 0.5; pr.parentsOwn = pr.hhHomes !== '0' && !owns; if (pr.parentsOwn) pr.hhOwner = pr.parents60 ? 'parent60' : 'other'; }
      if (pr.married && pr.marriedOn && pr.marriedOn < addYears(birth, 18)) pr.marriedOn = addYears(birth, 25);
      if (kids && pr.youngestBirth && pr.youngestBirth < addYears(birth, 18)) pr.youngestBirth = addYears(birth, 30);
      if (L.category === 'general' && isNewlywedTown(L)) { pr.townType = married ? null : pick(['pre', 'single', 'none']); pr.townInsurance = 0; pr.townFinOther = 0; pr.townOtherAsset = pick([0, 5000, 20000]); pr.townDebt = pick([0, 5000, 15000]); }
      pr.areaSince = pr.sidoOwnSince; pr.sidoSince = pr.sidoOwnSince;
      pr.hhIncomeYear = pr.income + pr.spouseIncome;
      if (pr.acctType === '') { delete pr.acctSince; pr.acctAmount = 0; pr.acctCount = null; pr.acctPaid = null; }
      const P = Object.assign({}, DEFAULT_PROFILE, pr); syncHome(P);
      const e = eligibility(L, P), sc = myScore(L, P), sps = spTypesFor(L);
      const spT = sps.length ? pick(sps) : null, sp = spT ? spJudge(L, P, spT) : null;
      const id = 'G' + String(i + 1).padStart(3, '0');
      cases.push({ id, listing: L.id, notice_id: L.id.split('-')[0], name: L.name, house_type: L.unit || L.id.split('-')[1], area_m2: L.area, kind: L.houseDtl === '국민' ? '공공(국민)' : '민영', stratum: st[0], supply_category: L.category === 'remainder' ? '무순위·재공급(사후접수)' : '일반 분양',
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
