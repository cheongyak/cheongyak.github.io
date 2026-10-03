// 판정 전후 비교 (2026-10-03 사용자 '최신 수정이 이전 정상값에 영향을 주지 않게'): 두 시점의 공고 데이터(listings.json)를 같은 화면 판정 함수로
// 판정 사례의 서로 다른 내 조건 전부에 돌려, 주택형 × 내 조건마다 판정 묶음(가능/확인 필요/불가)과 체크리스트 항목별 상태가 달라진 곳을 모은다.
// 데이터가 바뀌지 않은 주택형에서 판정이 바뀌면 '예상 밖'으로 따로 표시한다 (같은 입력이면 같은 판정이어야 함).
// 사용: NODE_PATH=$(npm root -g) node tools/qa/verdict_diff.cjs <이전 listings.json> [지금 listings.json(기본 docs/listings.json)] → evidence/qa/verdict-diff.json
//   이전 파일은 예: git show <커밋>:docs/listings.json > /tmp/base.json. 예상 밖이 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
const [basePath, curPath = join(DOCS, 'listings.json')] = process.argv.slice(2);
if (!basePath) { console.error('사용: node tools/qa/verdict_diff.cjs <이전 listings.json> [지금 listings.json]'); process.exit(2); }
const INPUT_SKIP = new Set(['mkt_note', 'jeonse_note', 'mkt_comps', 'jeonse_comps', 'notice_quotes', 'notice_pdf', 'map_query', 'nearby', 'area_comps', 'area_sp', 'checks']);   // 판정에 안 쓰는 설명·근거 필드

async function run(listingsPath, profiles) {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage({ viewport: { width: 390, height: 844 } }); const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = u.pathname === '/listings.json' ? listingsPath : join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html': 'text/html', '.json': 'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(400);
  const out = await page.evaluate(profiles => {
    const res = {};
    profiles.forEach((pr, pi) => {
      const P = Object.assign({}, DEFAULT_PROFILE, pr);
      LISTINGS.filter(L => !L.sample).forEach(L => {
        const e = eligibility(L, P);
        res[L.id + '|' + pi] = { bucket: eligBucket(L, P), items: Object.fromEntries(e.items.map(i => [i.k, i.s + ':' + (i.v || '')])), grade: typeof grade === 'function' ? String(grade(L)) : '' };
      });
    });
    return res;
  }, profiles);
  await b.close();
  return { out, errs };
}

(async () => {
  const cases = JSON.parse(readFileSync(join(ROOT, 'tests/judge/cases.json'), 'utf8'));
  const profiles = [...new Map(cases.map(c => [JSON.stringify(c.profile), c.profile])).values()];
  const A = await run(basePath, profiles), B = await run(curPath, profiles);
  const la = Object.fromEntries(JSON.parse(readFileSync(basePath, 'utf8')).map(x => [x.id, x]));
  const lb = Object.fromEntries(JSON.parse(readFileSync(curPath, 'utf8')).map(x => [x.id, x]));
  const inputDiff = id => { const a = la[id] || {}, b = lb[id] || {}; return [...new Set([...Object.keys(a), ...Object.keys(b)])].filter(k => !INPUT_SKIP.has(k) && JSON.stringify(a[k]) !== JSON.stringify(b[k])); };
  const changes = [], unexpected = [];
  for (const key of Object.keys(B.out)) {
    if (!A.out[key]) continue;
    const [id, pi] = key.split('|'), a = A.out[key], b = B.out[key];
    const items = [...new Set([...Object.keys(a.items), ...Object.keys(b.items)])].filter(k => a.items[k] !== b.items[k]).map(k => `${k}: ${a.items[k] || '-'} → ${b.items[k] || '-'}`);
    if (a.bucket === b.bucket && !items.length && a.grade === b.grade) continue;
    const why = inputDiff(id);
    const row = { id, name: (lb[id] || {}).name, profile: +pi, bucket: a.bucket === b.bucket ? a.bucket : `${a.bucket} → ${b.bucket}`, grade: a.grade === b.grade ? undefined : `${a.grade} → ${b.grade}`, items, changed_inputs: why };
    (why.length ? changes : unexpected).push(row);
  }
  const byNotice = {};
  for (const r of changes) { const n = r.id.split('-')[0]; byNotice[n] = byNotice[n] || { name: r.name, rows: 0, buckets: 0, inputs: new Set() }; byNotice[n].rows++; if (r.bucket.includes('→')) byNotice[n].buckets++; r.changed_inputs.forEach(k => byNotice[n].inputs.add(k)); }
  const summary = Object.fromEntries(Object.entries(byNotice).map(([n, v]) => [n, { name: v.name, rows: v.rows, bucket_changes: v.buckets, inputs: [...v.inputs] }]));
  const total = Object.keys(B.out).length;
  writeFileSync(join(ROOT, 'evidence/qa/verdict-diff.json'), JSON.stringify({ at: new Date().toISOString(), base: basePath, profiles: profiles.length, checked: total, changed: changes.length, unexpected: unexpected.length, by_notice: summary, unexpected_rows: unexpected.slice(0, 50), sample_changes: changes.slice(0, 40), transitions: Object.entries(changes.reduce((m, r) => { const k = r.id.split("-")[0] + " " + r.bucket; m[k] = (m[k] || 0) + 1; return m; }, {})).sort((a, b) => b[1] - a[1]), errors: [...A.errs, ...B.errs].slice(0, 5) }, null, 1) + '\n');
  console.log(`[판정 전후 비교] 주택형×내 조건 ${total}개 · 판정이 바뀐 곳 ${changes.length} (데이터가 바뀐 공고 ${Object.keys(summary).length}곳) · 예상 밖(데이터 그대로인데 판정 바뀜) ${unexpected.length}`);
  for (const [n, v] of Object.entries(summary)) console.log(`  ${n} ${v.name}: ${v.rows}곳 (묶음 바뀜 ${v.bucket_changes}) ← ${v.inputs.join(', ')}`);
  if (unexpected.length) unexpected.slice(0, 10).forEach(r => console.log('  예상 밖', r.id, r.profile, r.bucket, r.items.join(' / ')));
  process.exit(unexpected.length ? 1 : 0);
})();
