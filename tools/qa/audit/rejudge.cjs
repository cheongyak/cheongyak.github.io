// 감사 사례를 지금 앱으로 다시 판정 (프로필 수정 가능). 사용: node rejudge.cjs cases_full.json out.json [noacct]
const { chromium } = require('playwright');
const { readFileSync, existsSync, writeFileSync } = require('node:fs'); const { join, extname } = require('node:path');
const dir = process.cwd() + '/docs', [IN, OUT, MODE] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }); const p = await b.newPage();
  await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.abort();
    const f = join(dir, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: readFileSync(f), contentType: extname(f)==='.html'?'text/html':'application/json' }); });
  await p.goto('http://site.local/', { waitUntil: 'networkidle' }); await p.waitForTimeout(600);
  const cases = JSON.parse(readFileSync(IN, 'utf8'));
  const out = await p.evaluate(([cases, MODE]) => cases.map(c => {
    const L = LISTINGS.find(x => x.id === c.listing); if (!L) return { id: c.id, missing: true };
    const P = Object.assign({}, DEFAULT_PROFILE, c.profile); if (MODE === 'noacct' && P.acctType === '') P.acctType = 'none'; syncHome(P);
    const e = eligibility(L, P), sc = myScore(L, P), sp = c.sp_type ? spJudge(L, P, c.sp_type) : null;
    return { id: c.id, verdict: e.ok ? (e.unsure ? 'unsure' : 'ok') : e.rank2 ? (e.rank2Need ? 'unsure' : 'rank2') : 'no', bucket: eligBucket(L, P), items: e.items.map(x => [x.k, x.s, x.v]), score: sc.total, parts: sc.parts.map(x => x.v),
      sp: sp ? { type: c.sp_type, s: sp.s, stage: sp.stage && sp.stage[0], fail: sp.fail, warn: sp.warn } : null };
  }), [cases, MODE]);
  writeFileSync(OUT, JSON.stringify(out, null, 1)); console.log(out.length); await b.close();
})();
