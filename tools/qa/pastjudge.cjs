// 과거 공고 '그때 넣었다면' 판정 분포 확인 (기능: historical_judge). docs/archive/past-judge.json 을 화면 엔진(eligBucket·spJudge)으로 돌려
// 몇 가지 대표 조건별로 신청 가능/확인 필요/2순위/불가 개수와, 확인 필요가 나온 이유(공고문 읽음 여부)를 센다.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/pastjudge.cjs
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
(async () => {
const DOCS = join(__dirname, '../../docs');
const exe = existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined;
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const page = await browser.newPage();
await page.route('**/*', route => {
  const u = new URL(route.request().url());
  if (u.hostname !== 'judge.local') return route.abort();
  const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
  if (!existsSync(f)) return route.fulfill({ status: 404, body: '' });
  route.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' });
});
await page.goto('http://judge.local/', { waitUntil: 'networkidle' });
const PJ = JSON.parse(readFileSync(join(DOCS, 'archive/past-judge.json'), 'utf8'));
const cases = JSON.parse(readFileSync(join(__dirname, '../../tests/judge/cases.json'), 'utf8'));
const profiles = [...new Map(cases.map(c => [JSON.stringify(c.profile), c.profile])).values()].slice(0, 6);
const out = await page.evaluate(({ items, profiles }) => profiles.map(pr => {
  S.profile = Object.assign({}, DEFAULT_PROFILE, pr); save(); const p = S.profile;
  const n = {}, why = {};
  items.forEach(x => { const L = fromApi(x), b = eligBucket(L, p); n[b] = (n[b] || 0) + 1;
    if (b === 'unsure') { const k = (x.notice_read ? '공고문 읽음' : '공고문 못 읽음'); why[k] = (why[k] || 0) + 1; } });
  return { profile: pr, n, why };
}), { items: PJ.items, profiles });
out.forEach(o => console.log(JSON.stringify(o.n), JSON.stringify(o.why), JSON.stringify(o.profile).slice(0, 140)));
await browser.close();
})();
