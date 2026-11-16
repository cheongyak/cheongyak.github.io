// 첫 화면 링크 검사 (2026-11-16 운영자: 애드센스 미승인 대응 — 기능 guide_pages·home_footer).
// 공고 목록 화면에 ① 청약 가이드 바로가기(일반 <a href="/guide/">) ② 맨 아래 사이트 링크(/story/ /about/ /privacy/ /terms/, 일반 <a>)가 있고,
// 링크가 가리키는 정적 페이지가 실제로 있으며, 스위치를 끄면 둘 다 사라지는지, 390px 에서 가로로 넘치지 않는지 본다.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/home_links.cjs [스크린샷.png]
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const DOCS = join(__dirname, '../../docs');
async function run(b, feats, shot) {
  const page = await b.newPage({ viewport: { width: 390, height: 844 } });
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    let body = readFileSync(f);
    if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = Object.assign({}, c.features, feats); body = JSON.stringify(c); }
    r.fulfill({ status: 200, body, contentType: { '.html': 'text/html', '.json': 'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => typeof LISTINGS !== 'undefined' && LISTINGS.length > 0, null, { timeout: 15000 }).catch(() => {});
  const out = await page.evaluate(() => { S.view = 'feed'; render();
    const g = document.querySelector('#app a.guide-entry'), f = document.querySelector('#app nav.sitefoot');
    return { view: S.view, guide: g ? g.getAttribute('href') : null, guideH: g ? g.getBoundingClientRect().height : 0, foot: f ? [...f.querySelectorAll('a')].map(a => a.getAttribute('href')) : [],
             over: document.documentElement.scrollWidth - document.documentElement.clientWidth,
             other: (go('me'), document.querySelectorAll('#app nav.sitefoot, #app a.guide-entry').length) }; });
  if (shot) { await page.evaluate(() => { go('feed'); }); await page.screenshot({ path: shot }); await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight)); await page.screenshot({ path: shot.replace('.png', '-foot.png') }); }
  await page.close();
  return Object.assign(out, { errs });
}
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const on = await run(b, { guide_pages: true, home_footer: true, static_pages: true }, process.argv[2]);
  const off = await run(b, { guide_pages: false, home_footer: false });
  const fails = [];
  if (on.guide !== '/guide/') fails.push('공고 목록에 청약 가이드 바로가기(<a href="/guide/">)가 없음');
  if (on.guideH < 44) fails.push(`청약 가이드 바로가기 높이 ${on.guideH}px (44px 이상이어야 함)`);
  for (const h of ['/guide/', '/story/', '/about/', '/privacy/', '/terms/']) {
    if (!on.foot.includes(h)) fails.push(`맨 아래 사이트 링크에 ${h} 가 없음`);
    if (!existsSync(join(DOCS, h, 'index.html'))) fails.push(`${h} 정적 페이지가 없음`);
  }
  if (on.over > 0) fails.push(`가로로 ${on.over}px 넘침`);
  if (on.other) fails.push('공고 목록이 아닌 화면(내 조건)에 가이드 바로가기·사이트 링크가 있음');
  if (off.guide || off.foot.length) fails.push('스위치를 껐는데 가이드 바로가기·사이트 링크가 보임');
  for (const r of [on, off]) if (r.errs.length) fails.push('화면 오류 ' + r.errs[0]);
  console.log(`[첫 화면 링크 검사] 가이드 바로가기 ${on.guide} · 사이트 링크 ${on.foot.join(' ')} · 스위치 끔 → ${off.guide || off.foot.length ? '보임' : '없음'} · 실패 ${fails.length}` + (fails.length ? '\n  ' + fails.join('\n  ') : ''));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})();
