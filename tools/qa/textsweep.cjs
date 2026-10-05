// 화면 문구 훑기: 무작위 프로필 여러 개로 모든 화면(목록·상세·자금·인터뷰 단계·가점 컷·등급·내 조건·안내·문서)을 그려
// 보이는 문장을 모은다. 숫자는 #으로 바꿔 같은 틀은 하나로 묶고, 나온 횟수와 예시 화면을 남긴다 → 문구 검토용.
// 사용: NODE_PATH=... node tools/qa/textsweep.cjs <출력.json> [프로필 수=12] [시드]
const { chromium } = require('playwright');
const { readFileSync, existsSync, writeFileSync } = require('node:fs'); const { join, extname } = require('node:path');
const dir = join(__dirname, '../../docs'), OUT = process.argv[2], N = +process.argv[3] || 12, SEED = +process.argv[4] || 4242;
const T = { '.html':'text/html', '.json':'application/json', '.js':'text/javascript' };
(async () => {
  const b = await chromium.launch(existsSync('/opt/pw-browsers/chromium') ? { executablePath: '/opt/pw-browsers/chromium' } : {});
  const p = await b.newPage({ viewport: { width: 390, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.abort();
    const f = join(dir, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: readFileSync(f), contentType: T[extname(f)] || 'application/octet-stream' }); });
  await p.goto('http://site.local/?lh=preview', { waitUntil: 'networkidle' }); await p.waitForTimeout(800);   // ?lh=preview: LH 임대 화면도 훑음 (기능 lh_rental)
  await p.evaluate(() => new Promise(res => { loadRental(); const t = setInterval(() => { if (RENTAL || RENTAL_STATE === 'error') { clearInterval(t); res(); } }, 50); }));
  const res = await p.evaluate(([N, SEED]) => {
    let s = SEED; const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648;
    const pick = a => a[Math.floor(rnd() * a.length)], int = (a, b2) => a + Math.floor(rnd() * (b2 - a + 1));
    const day = (y0, y1) => `${int(y0, y1)}-${String(int(1, 12)).padStart(2, '0')}-${String(int(1, 28)).padStart(2, '0')}`;
    const SIDO = { '서울':['강남구','노원구','마포구'], '경기':['광명시','성남시','양주시','수원시'], '인천':['계양구','서구'], '부산':['강서구','해운대구'], '울산':['남구'], '충남':['천안시'], '전북':['전주시'] };
    const prof = () => { const sido = pick(Object.keys(SIDO)), married = rnd() < 0.6, kids = married ? pick([0, 1, 2, 3]) : 0, owns = rnd() < 0.2;
      const pr = { homeSido: sido, homeSigun: pick(SIDO[sido]), sidoOwnSince: day(2005, 2026).replace(/-\d\d$/, '-01'), household: pick(['head','head','parents','spouse']),
        selfOwn: owns, married, marriedOn: married ? day(2012, 2025) : '', spouseOwn: false, acctType: pick(['all','all','deposit']), acctSince: day(2008, 2025),
        acctAmount: pick([200, 300, 600, 1500]), acctCount: int(3, 150), acctPaid: pick([300, 1500, 3000]), hhHomes: owns ? '1' : pick(['0','0','1']), win5y: rnd() < 0.1,
        everWin: 'none', recentWin: false, birth: day(1965, 2001), dependents: married ? 1 + kids : 0, kidsMinor: kids, youngestBirth: kids ? day(2016, 2026) : '', pregnant: rnd() < 0.1,
        hhSize: (married ? 2 : 1) + kids, kidsOnDeed: kids, eldersOnDeed: pick([0, 0, 1, null]), elders1y: true, income: pick([3000, 5000, 8000]), spouseIncome: married ? pick([0, 3000]) : 0,
        realEstate: pick([0, 0, 20000, 40000]), carValue: pick([0, 2000, 5000]), hhNeverOwned: !owns, taxYears5: rnd() < 0.7, elder65: rnd() < 0.15, cash: pick([3000, 10000, 30000, 80000]),
        liquid: pick([0, 5000]), deposit: pick([0, 20000]) };
      if (pr.household === 'head') pr.headSince = day(2010, 2025); pr.areaSince = pr.sidoOwnSince; pr.sidoSince = pr.sidoOwnSince; pr.hhIncomeYear = pr.income + pr.spouseIncome;
      if (rnd() < 0.25) Object.keys(pr).forEach(k => { if (rnd() < 0.5) delete pr[k]; });   // 일부 비운 프로필
      return pr; };
    const profiles = [null, {}, ...Array.from({ length: N }, prof)];
    const bag = new Map();
    const take = (where) => { const t = document.querySelector('main, #app, body').innerText;
      t.split(/\n+/).map(x => x.trim()).filter(x => x.length >= 6 && /[가-힣]/.test(x)).forEach(line => {
        line.split(/(?<=[.?!요다])\s+(?=[가-힣A-Z(])/).forEach(sen => { const k = sen.replace(/\d[\d,.]*/g, '#'); const v = bag.get(k) || { n:0, ex:sen, at:where }; v.n++; bag.set(k, v); }); }); };
    const LS = LISTINGS.filter(L => !L.sample);
    profiles.forEach((pr, pi) => {
      try { localStorage.clear(); localStorage.setItem('cy-lh-preview', '1'); } catch (e) {}
      S.profile = Object.assign({}, DEFAULT_PROFILE, pr || {}); if (pr) { syncHome(S.profile); save(); }
      for (const v of ['feed', 'grades', 'me', 'about', 'alerts', 'updates', 'compare', 'trend']) { try { S.id = null; go(v); take(pi + '|' + v); } catch (e) {} }
      const sample = pi < 2 ? LS : LS.filter(() => rnd() < 0.35);
      for (const L of sample) { S.id = L.id; try { go('detail'); take(pi + '|detail|' + L.id); go('plan'); take(pi + '|plan|' + L.id); } catch (e) {} }
      // LH 임대: 분류 탭 3개 목록, 공고 상세(앞 2개 조건은 전부, 나머지는 일부), 답하기 창
      for (const c of ['rent', 'youth']) { try { S.rcat = c; go('rental'); take(pi + '|rental|' + c); } catch (e) {} }
      for (const N of ((RENTAL && RENTAL.notices) || []).filter(() => pi < 2 || rnd() < 0.35)) { try { S.rid = N.id; S.rq = null; go('rdetail'); take(pi + '|rdetail|' + N.id);
        [...document.querySelectorAll('[data-rq]')].map(x => x.dataset.rq).forEach(q => { S.rq = q; render(); take(pi + '|rq|' + N.id); }); S.rq = null; } catch (e) {} }
      if (pi === 2) { try { visibleSteps().forEach((st, i) => { S.step = i; go('onboard'); take('onboard|' + stepKey(st)); }); } catch (e) {} }
    });
    return [...bag.entries()].map(([k, v]) => ({ t: k, n: v.n, ex: v.ex, at: v.at }));
  }, [N, SEED]);
  writeFileSync(OUT, JSON.stringify(res, null, 1)); console.log('문장 틀', res.length, '오류', errs.length, errs.slice(0, 3));
  await b.close();
})();
