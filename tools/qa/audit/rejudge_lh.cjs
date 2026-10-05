// LH 임대 감사 사례를 지금 앱으로 다시 판정: NODE_PATH=$(npm root -g) node tools/qa/audit/rejudge_lh.cjs <감사폴더> [출력=app.json]
const { chromium } = require('playwright');
const { readFileSync, existsSync, writeFileSync } = require('node:fs'); const { join, extname } = require('node:path');
const dir = process.cwd() + '/docs', D = process.argv[2], OUT = process.argv[3] || 'app.json';
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }); const p = await b.newPage();
  await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.abort();
    const f = join(dir, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: readFileSync(f), contentType: extname(f)==='.html'?'text/html':'application/json' }); });
  await p.goto('http://site.local/', { waitUntil: 'networkidle' });
  await p.evaluate(() => new Promise(res => { loadRental(); const t = setInterval(() => { if (RENTAL) { clearInterval(t); res(); } }, 50); }));
  const cases = JSON.parse(readFileSync(join(D, 'cases.json')));
  const app = await p.evaluate(cases => cases.map(c => { const N = RENTAL.notices.find(x => x.id === c.notice_id); const J = rentalJudge(N, Object.assign({}, DEFAULT_PROFILE, c.profile));
    return { id: c.id, groups: J.groups.map(g => ({ group: g.key, s: g.s, items: g.items.map(x => x.s + ':' + x.t) })) }; }), cases);
  writeFileSync(join(D, OUT), JSON.stringify(app, null, 1)); console.log(app.length); await b.close();
})();
