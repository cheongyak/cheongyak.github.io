// 화면 글자 스냅샷 회귀 (2026-10-02 MASTER QA 22항): 고정 데이터(tests/judge/listings.json 고정 공고)·고정 날짜(2026-10-02)·고정 내 조건 3개로
// 목록 카드·상세 맨 위 판정·일반공급 칸 머리·특별공급 칸 머리의 글자를 뽑아 tests/qa/snapshots.json 과 비교한다. 잘못된 배지·숫자가 다른 칸으로 가거나 문구가 바뀌면 걸린다.
// 일부러 바꾼 거면 --update 로 다시 쓰고 커밋한다 (engine_lock 과 같은 방식). 사진은 evidence/qa/shots/ 에 남긴다(사람 확인용, 비교 안 함).
// 사용: NODE_PATH=$(npm root -g) node tools/qa/snapshot.cjs [--update]
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync, mkdirSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs'), BASE_F = join(ROOT, 'tests/qa/snapshots.json'), SHOTS = join(ROOT, 'evidence/qa/shots');
const PROFILES = {
  '서울 신혼 세대주': { household:'head', headSince:'2015-01-01', selfOwn:false, spouseOwn:false, hhHomes:'0', hhNeverOwned:true, win5y:false, recentWin:false, everWin:'none', acctType:'all', acctSince:'2014-01-01', acctAmount:1500, acctCount:120, acctPaid:2000, birth:'1990-03-01', homeSido:'서울', homeSigun:'마포구', sidoOwnSince:'2015-01-01', sidoSince:'2015-01-01', areaSince:'2015-01-01', married:true, marriedOn:'2023-05-01', dependents:2, kidsMinor:1, kidsOnDeed:1, eldersOnDeed:0, youngestBirth:'2025-06-01', pregnant:false, hhSize:3, income:5000, spouseIncome:0, hhIncomeYear:5000, realEstate:0, carValue:1000, cash:3000, taxYears5:true, elder65:false },
  '인천 1인 세대원': { household:'parents', parents60:true, parentsOwn:false, selfOwn:false, hhHomes:'0', win5y:false, everWin:'none', acctType:'all', acctSince:'2020-01-01', acctAmount:300, acctCount:30, acctPaid:500, birth:'1997-01-01', homeSido:'인천', homeSigun:'계양구', sidoOwnSince:'2010-01-01', sidoSince:'2010-01-01', areaSince:'2010-01-01', married:false, dependents:0, kidsMinor:0, kidsOnDeed:0, eldersOnDeed:2, elders1y:2, hhSize:3, income:3500, hhIncomeYear:9000, realEstate:0, carValue:0 },
  '조건 없음': null };
(async () => {
  const fixtures = JSON.parse(readFileSync(join(ROOT, 'tests/judge/listings.json'), 'utf8')).filter(x => !/-REG$|SPELDER|A60|A6001|A85|A8501/.test(x.id));
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const snap = {}; mkdirSync(SHOTS, { recursive: true });
  for (const [pn, pr] of Object.entries(PROFILES)) {
    const page = await b.newPage({ viewport: { width: 390, height: 900 } }); const errs = []; page.on('pageerror', e => errs.push(e.message));
    await page.clock.install({ time: new Date('2026-10-02T03:00:00Z') });
    await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
      if (u.pathname === '/listings.json') return r.fulfill({ status: 200, body: JSON.stringify(fixtures), contentType: 'application/json' });
      const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
      r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
    if (pr) await page.addInitScript(p => localStorage.setItem('cy-profile', JSON.stringify(p)), '_set' in pr ? pr : Object.assign({}, pr, { _set: Object.keys(pr) }));   // 적어 둔 칸 = 넣은 칸 (2026-10-06)
    await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.clock.runFor(1500);
    const out = await page.evaluate(fx => { LISTINGS = fx.map(x => fromApi(x)); const r = {};
      const T = el => el ? el.innerText.replace(/\s+/g, ' ').trim() : '';
      for (const L of LISTINGS) { const d = document.createElement('div'); d.innerHTML = listingCard(L, grade(L));
        S.view = 'detail'; S.id = L.id; render();
        const cards = [...document.querySelectorAll('section.card')];
        r[L.id] = { card: T(d), hero: T(document.querySelector('.rhero')), general: T(document.querySelector('.ckcard .row')), special: T(cards.find(c => /특별공급/.test((c.querySelector('h2') || {}).textContent || ''))?.querySelector('.row')) }; }
      return r; }, fixtures);
    snap[pn] = out;
    if (errs.length) snap[pn]._errors = errs.slice(0, 5);
    await page.evaluate(id => { S.view = 'detail'; S.id = id; render(); window.scrollTo(0, 0); }, fixtures[0].id);
    await page.screenshot({ path: join(SHOTS, `${pn.replace(/\s+/g, '_')}.png`) });
    await page.close();
  }
  await b.close();
  if (process.argv.includes('--update') || !existsSync(BASE_F)) { writeFileSync(BASE_F, JSON.stringify(snap, null, 1) + '\n'); console.log('[QA 스냅샷] 기준을 새로 썼어요'); return; }
  const base = JSON.parse(readFileSync(BASE_F, 'utf8')), diffs = [];
  for (const pn of Object.keys(snap)) for (const id of new Set([...Object.keys(snap[pn]), ...Object.keys(base[pn] || {})])) {
    const a = (base[pn] || {})[id], c = snap[pn][id];
    if (JSON.stringify(a) !== JSON.stringify(c)) for (const k of ['card', 'hero', 'general', 'special']) if (!a || !c || a[k] !== c[k]) diffs.push({ profile: pn, id, part: k, was: a && a[k], now: c && c[k] });
  }
  writeFileSync(join(ROOT, 'evidence/qa/snapshot.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), diffs: diffs.length, examples: diffs.slice(0, 30) }, null, 1) + '\n');
  console.log(`[QA 스냅샷] 고정 공고 ${Object.keys(snap['조건 없음']).length}개 × 조건 ${Object.keys(snap).length}개 · 바뀐 곳 ${diffs.length}`);
  diffs.slice(0, 8).forEach(d => console.log('  ', d.profile, d.id, d.part, '\n     전:', (d.was || '').slice(0, 120), '\n     후:', (d.now || '').slice(0, 120)));
  process.exit(diffs.length ? 1 : 0);
})();
