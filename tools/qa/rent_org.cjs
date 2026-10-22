// 임대 기관별 거르기 화면 검사 (기능 rent_org_filter, 2026-10-22 사용자 'lh/sh/gh 분류해서 누르면 공고카드들 필터되도록').
// 390px 에서: 기관 칩이 보이는지, 칩을 누르면 그 기관 카드만 남는지(카드 머리의 기관 글자로 확인), 칩 숫자 = 걸러진 카드 수, 다시 누르면 전체, 유형 거르기와 함께 써도 맞는지.
// 실행: NODE_PATH=$(npm root -g) node tools/qa/rent_org.cjs [스크린숏 폴더]   (실패하면 종료 코드 1)
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const DOCS = path.join(__dirname, '..', '..', 'docs'), OUT = process.argv[2] || null;
(async () => {
  const b = await chromium.launch({ executablePath: fs.existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const pg = await b.newPage({ viewport: { width: 390, height: 844 } });
  const errs = [], fails = [];
  pg.on('pageerror', e => errs.push(e.message));
  await pg.route('**/*', async r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'qa.local') return r.abort();
    const f = path.join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!fs.existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: fs.readFileSync(f), contentType: f.endsWith('.html') ? 'text/html' : f.endsWith('.mjs') ? 'text/javascript' : 'application/json' });
  });
  await pg.goto('http://qa.local/', { waitUntil: 'networkidle' });
  await pg.evaluate(() => { S.rcat = 'rent'; go('rental'); });
  await pg.waitForFunction(() => typeof RENTAL_STATE !== 'undefined' && RENTAL_STATE === 'ok', null, { timeout: 20000 });
  await pg.evaluate(() => render()); await pg.waitForTimeout(400);
  const chips = await pg.$$eval('.rorg .chip', els => els.map(e => ({ k: e.dataset.rorg, t: e.innerText.trim() })));
  if (chips.length < 3) fails.push('기관 칩이 2개 이하: ' + JSON.stringify(chips));
  const cardOrgs = () => pg.$$eval('.card.lh, .card.rental, button[data-ropen], [data-ropen]', els => [...new Set(els.map(e => e.closest('[data-ropen]') || e))].map(e => (e.querySelector('.small.muted b') || {}).innerText || '').filter(Boolean));
  const total = (await cardOrgs()).length;
  for (const c of chips.filter(c => c.k)) {
    await pg.click(`.rorg .chip[data-rorg="${c.k}"]`); await pg.waitForTimeout(250);
    const orgs = await cardOrgs(), want = Number((c.t.match(/(\d+)\s*$/) || [])[1]);
    const ok = orgs.length > 0 && orgs.every(o => o === c.k) && orgs.length === want;
    console.log(`[임대 기관 거르기·${ok ? '통과' : '실패'}] ${c.k}: 카드 ${orgs.length}개 (칩 숫자 ${want})${orgs.some(o => o !== c.k) ? ' · 다른 기관 섞임 ' + [...new Set(orgs)].join(',') : ''}`);
    if (!ok) fails.push(c.k);
    if (OUT && c.k === 'GH') await pg.screenshot({ path: OUT + '/rent-org-gh.png' });
    await pg.click(`.rorg .chip[data-rorg="${c.k}"]`); await pg.waitForTimeout(250);   // 다시 누르면 전체
    const back = (await cardOrgs()).length;
    if (back !== total) fails.push(`${c.k} 다시 누름: ${back} ≠ 전체 ${total}`);
  }
  if (OUT) { await pg.evaluate(() => window.scrollTo(0, 0)); await pg.screenshot({ path: OUT + '/rent-org-all.png' }); }
  await b.close();
  if (errs.length) fails.push('화면 오류 ' + errs.join('; '));
  console.log(`[임대 기관 거르기] 칩 ${chips.map(c => c.t).join(' / ')} · 전체 카드 ${total} · 실패 ${fails.length}${fails.length ? ' — ' + fails.join(' | ') : ''}`);
  fs.writeFileSync(path.join(__dirname, '..', '..', 'evidence', 'qa', 'rent-org.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), chips: chips.map(c => c.t), total, fails }, null, 1) + '\n');
  process.exit(fails.length ? 1 : 0);
})();
