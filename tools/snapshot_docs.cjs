// 검색엔진·광고 심사용 정적 문서 조각 만들기 (기능: static_pages)
// 앱(docs/index.html)의 문서 화면(만든 이유·이용 안내·이용약관·개인정보처리방침·업데이트 내역)을 그대로 그려 HTML 조각으로 저장한다.
// tools/build_static.py 가 이 조각과 가이드 페이지를 /story/ 등 별도 주소의 일반 HTML 페이지로 만든다.
// 사용: node tools/snapshot_docs.cjs   → tools/static_fragments.json
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');

(async () => {
const ROOT = join(__dirname, '..'), DOCS = join(ROOT, 'docs');
const exe = existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined;
const TYPES = { '.html':'text/html', '.json':'application/json', '.png':'image/png', '.webmanifest':'application/manifest+json', '.txt':'text/plain' };
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const page = await browser.newPage({ viewport: { width: 420, height: 900 } });
const errors = [];
page.on('pageerror', e => errors.push(e.message));
await page.route('**/*', route => {
  const u = new URL(route.request().url());
  if (u.hostname !== 'static.local') return route.abort();
  const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
  if (!existsSync(f)) return route.fulfill({ status: 404, body: '' });
  route.fulfill({ status: 200, body: readFileSync(f), contentType: TYPES[extname(f)] || 'application/octet-stream' });
});
await page.goto('http://static.local/', { waitUntil: 'networkidle' });
await page.waitForTimeout(600);
const out = {};
for (const v of ['story', 'about', 'terms', 'privacy', 'updates']) {
  await page.evaluate(v => go(v), v);
  await page.waitForTimeout(700);
  out[v] = await page.evaluate(() => {
    const root = document.getElementById('app').cloneNode(true);
    root.querySelectorAll('.top, [data-action], .bell, script').forEach(n => n.remove());
    // 앱 안 이동 버튼 → 정적 페이지 링크
    const MAP = { story:'/story/', terms:'/terms/', privacy:'/privacy/', about:'/about/', updates:'/updates/', feed:'/', grades:'/', trend:'/' };
    root.querySelectorAll('[data-go]').forEach(b => { const a = document.createElement('a'); a.href = MAP[b.dataset.go] || '/'; a.className = b.className; a.innerHTML = b.innerHTML; b.replaceWith(a); });
    root.querySelectorAll('button').forEach(b => b.remove());
    return root.innerHTML;
  });
}
writeFileSync(join(__dirname, 'static_fragments.json'), JSON.stringify(out, null, 1));
// 기능 seo_content (2026-11-04): 공고 정적 페이지의 등급·판정 이유는 화면 엔진(grade·gLabel·marginText·mktHow·statusOf)이 낸 값만 쓴다 — 새 규칙을 만들지 않는다.
// 꺼져 있으면 만들지 않는다 (tools/seo_engine.json 은 tools/seo_pages.py 만 읽음)
const seo = await page.evaluate(() => {
  if (!on('seo_content')) return null;
  const r = v => v == null || !isFinite(v) ? null : Math.round(v * 1000) / 1000;
  const rows = {};
  for (const L of LISTINGS) {
    if (L.sample) continue;
    const m = grade(L);
    rows[L.id] = { g: m.g, label: gLabel(L, m), margin: marginText(m), lo: r(m.lo), hi: r(m.hi), rate: r(m.rate), cost: r(m.cost), tax: r(m.tax), base: r(m.base),
      lease: m.lease ? { land: r(m.lease.land), real: r(m.lease.real), lo: r(m.lease.lo), hi: r(m.lease.hi) } : null,
      how: mktHow(L), status: statusOf(L), rental: isRental(L), kind: kindOf(L), price_word: priceWord(L) };
  }
  return { today: TODAY, rules: { lottoAbs: RULES.lottoAbs, lottoRate: RULES.lottoRate, considerAbs: RULES.considerAbs },
    names: { lotto: GNAME.lotto, consider: GNAME.consider, flat: GNAME.flat, pass: GNAME.pass, unknown: GNAME.unknown }, rows };
});
const SEO = join(__dirname, 'seo_engine.json');
if (seo) writeFileSync(SEO, JSON.stringify(seo));
else if (existsSync(SEO)) require('node:fs').unlinkSync(SEO);
console.log('[정적 문서] 조각 ' + Object.keys(out).length + '개' + (seo ? ' · 엔진 결과 ' + Object.keys(seo.rows).length + '개 (seo_content)' : '') + (errors.length ? ' · 화면 오류 ' + errors.join(' | ') : ''));
await browser.close();
process.exit(errors.length ? 1 : 0);
})();
