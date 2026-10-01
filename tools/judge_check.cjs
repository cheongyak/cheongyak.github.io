// 판정 검증 사례 실행 (기능: judge_cases): tests/judge/cases.json 의 기대값과 화면 판정 엔진(docs/index.html)의 결과를 비교한다.
// 사용: node tools/judge_check.cjs [--chromium /path/to/chrome]   (playwright 필요)
// 결과: 표준 출력 요약 + docs/judge-status.json, 하나라도 다르면 종료 코드 1
const { chromium } = require('playwright');   // NODE_PATH 로 전역 설치본도 찾는다
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');

(async () => {
const ROOT = join(__dirname, '..');
const DOCS = join(ROOT, 'docs');
const cases = JSON.parse(readFileSync(join(ROOT, 'tests/judge/cases.json'), 'utf8'));
const listings = JSON.parse(readFileSync(join(ROOT, 'tests/judge/listings.json'), 'utf8'));
const exe = process.argv.includes('--chromium') ? process.argv[process.argv.indexOf('--chromium') + 1] : (existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined);
const TYPES = { '.html':'text/html', '.json':'application/json', '.js':'text/javascript', '.png':'image/png', '.webmanifest':'application/manifest+json', '.txt':'text/plain' };

const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message));
await page.route('**/*', route => {
  const u = new URL(route.request().url());
  if (u.hostname !== 'judge.local') return route.abort();
  const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
  if (!existsSync(f)) return route.fulfill({ status: 404, body: '' });
  route.fulfill({ status: 200, body: readFileSync(f), contentType: TYPES[extname(f)] || 'application/octet-stream' });
});
await page.goto('http://judge.local/', { waitUntil: 'networkidle' });
await page.waitForTimeout(500);

const results = await page.evaluate(({ cases, listings }) => {
  const byId = Object.fromEntries(listings.map(x => [x.id, fromApi(x)]));
  const out = [];
  for (const c of cases) {
    const L = byId[c.listing];
    S.profile = Object.assign({}, DEFAULT_PROFILE, c.profile); save();
    const p = S.profile;
    let got;
    try {
      if (c.fn === 'score') got = { parts: myScore(L, p).parts.map(x => x.v) };
      else if (c.fn === 'sp') { const r = spJudge(L, p, c.type); got = { s: r.s, ...(c.expect.stage ? { stage: r.stage ? r.stage[0] : null } : {}) }; }
      else if (c.fn === 'acct') { const it = accountItems(L, p) || []; got = { '가입기간': (it.find(i => i.k === '청약통장 가입기간') || {}).s, '예치금': (it.find(i => i.k === '예치금 (민영)') || {}).s }; }
      else if (c.fn === 'pubgen') { const it = pubGeneralItems(L, p); got = { '소득': (it.find(i => i.k.startsWith('소득')) || {}).s }; }
      else if (c.fn === 'town') { const it = townItems(L, p); got = {}; for (const k of Object.keys(c.expect)) got[k] = (it.find(i => i.k === k + ' (신혼희망타운)') || {}).s; }
      else if (c.fn === 'bucket') got = { b: eligBucket(L, p) };
      else if (c.fn === 'item') { const it = c.item === '거주지' ? residenceItem(L, p) : eligibility(L, p).items.find(i => i.k === c.item); got = { s: it ? it.s : 'none' }; }
      else if (c.fn === 'home') { const it = eligibility(L, p).items.find(i => i.k === '무주택 세대') || {}; got = { s: it.s }; }
      else if (c.fn === 'residence') { const r = residenceItem(L, p); got = { s: r.s, v: r.v.includes(c.expect.v) ? c.expect.v : r.v }; }
    } catch (e) { got = { error: e.message }; }
    out.push({ id: c.id, ok: JSON.stringify(got) === JSON.stringify(c.expect), got, expect: c.expect, basis: c.basis });
  }
  return out;
}, { cases, listings });

const bad = results.filter(r => !r.ok);
const status = { at: new Date().toISOString(), total: results.length, passed: results.length - bad.length, failed: bad.map(r => ({ id: r.id, expect: r.expect, got: r.got, basis: r.basis })), pageErrors: errors };
writeFileSync(join(DOCS, 'judge-status.json'), JSON.stringify(status, null, 1) + '\n');
console.log(`[판정 검증] 사례 ${results.length}건 중 ${results.length - bad.length}건 일치` + (bad.length ? ` · 불일치 ${bad.length}건` : ''));
for (const r of bad) console.log(`[판정 검증·불일치] ${r.id}: 기대 ${JSON.stringify(r.expect)} ≠ 화면 ${JSON.stringify(r.got)} (${r.basis})`);
if (errors.length) console.log('[판정 검증·화면 오류] ' + errors.join(' | '));
await browser.close();
process.exit(bad.length || errors.length ? 1 : 0);
})();
