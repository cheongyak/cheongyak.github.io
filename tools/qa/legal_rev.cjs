// 개인정보처리방침 개정 예고·시행 검사 (2026-11-18 운영자: 방침 1항 '인터뷰에 입력한' → '내 조건에 입력한', 방침 11항대로 7일 전 예고).
// 예고 기간(시행 전날)과 시행일 두 날짜로 화면을 그려 본다: 시행 전 — 방침 예고 카드·목록 한 줄('개인정보처리방침이 바뀌어요')·본문은 지금 문구·바뀐 뒤 전문은 새 문구,
// 약관에는 예고 카드 없음 / 시행일 — 예고 사라짐·본문 새 문구·시행일과 개정 이력에 그 날짜.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/legal_rev.cjs [스크린샷.png]
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const DOCS = join(__dirname, '../../docs');
const CFG = JSON.parse(readFileSync(join(DOCS, 'config.json'), 'utf8'));
const REV = (CFG.privacy_rev || {}).date;
const dayBefore = d => { const t = new Date(d + 'T12:00:00+09:00'); t.setDate(t.getDate() - 1); return t.toISOString().slice(0, 10); };
async function run(b, day, shot) {
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  await page.clock.setFixedTime(new Date(day + 'T10:00:00+09:00'));
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html': 'text/html', '.json': 'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => typeof LISTINGS !== 'undefined' && LISTINGS.length > 0, null, { timeout: 15000 }).catch(() => {});
  const feed = await page.evaluate(() => (document.querySelector('#app .legalline') || {}).innerText || '');
  await page.evaluate(() => go('privacy')); await page.waitForTimeout(500);
  const pv = await page.evaluate(() => { const card = document.querySelector('#app .legalnote'); const full = card ? card.querySelector('.legalbody').textContent : '';
    if (card) card.remove(); const t = document.querySelector('#app').innerText;
    return { card: card ? card.innerText.slice(0, 300) : '', full, body: t, over: document.documentElement.scrollWidth - document.documentElement.clientWidth }; });
  if (shot) { await page.evaluate(() => go('privacy')); await page.waitForTimeout(300); await page.screenshot({ path: shot, fullPage: false }); }
  await page.evaluate(() => go('terms')); await page.waitForTimeout(400);
  const terms = await page.evaluate(() => !!document.querySelector('#app .legalnote'));
  await ctx.close();
  return { feed, pv, terms, errs };
}
(async () => {
  if (!REV) { console.log('[방침 개정 검사] privacy_rev 없음 — 건너뜀'); return; }
  const b = await chromium.launch();
  const pre = await run(b, dayBefore(REV), process.argv[2]), post = await run(b, REV);
  const fails = [], has = (t, s) => t.includes(s);
  if (!has(pre.pv.card, '개정 예고') || !has(pre.pv.card, '내 조건에 입력한')) fails.push('시행 전: 방침 예고 카드가 없거나 바뀌는 점이 없음');
  if (!has(pre.feed, '개인정보처리방침이 바뀌어요') || has(pre.feed, '이용약관')) fails.push('시행 전: 목록 한 줄 ' + JSON.stringify(pre.feed));
  if (!has(pre.pv.body, '인터뷰에 입력한 거주 지역') || has(pre.pv.body, '내 조건에 입력한 거주 지역')) fails.push('시행 전: 본문이 지금 문구가 아님');
  if (!has(pre.pv.full, '내 조건에 입력한 거주 지역') || /인터뷰/.test(pre.pv.full) || !has(pre.pv.full, REV + ' 개정 (표현 정비)')) fails.push('시행 전: 바뀐 뒤 전문에 새 문구·개정 이력이 없음');
  if (has(pre.pv.body, REV)) fails.push('시행 전: 지금 시행 본문에 시행일 ' + REV + ' 이 보임');
  if (pre.terms) fails.push('시행 전: 약관에 예고 카드가 보임(약관은 안 바뀜)');
  if (post.pv.card || post.feed) fails.push('시행일: 예고가 남아 있음');
  if (!has(post.pv.body, '내 조건에 입력한 거주 지역') || /인터뷰/.test(post.pv.body)) fails.push('시행일: 본문에 \'인터뷰\'가 남아 있음 ' + JSON.stringify((post.pv.body.match(/.{0,30}인터뷰.{0,20}/) || [''])[0]));
  if (!has(post.pv.body, '시행일 ' + REV) || !has(post.pv.body, REV + ' 개정 (표현 정비)')) fails.push('시행일: 시행일·개정 이력이 없음');
  for (const r of [pre, post]) { if (r.errs.length) fails.push('화면 오류 ' + r.errs[0]); if (r.pv.over > 0) fails.push(`가로로 ${r.pv.over}px 넘침`); }
  console.log(`[방침 개정 검사] 시행 ${REV} · 시행 전 예고 ${pre.pv.card ? '보임' : '없음'} · 시행일 본문 ${has(post.pv.body, '내 조건에 입력한') ? '새 문구' : '옛 문구'} · 실패 ${fails.length}` + (fails.length ? '\n  ' + fails.join('\n  ') : ''));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})();
