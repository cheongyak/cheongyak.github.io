// 공급유형 표시 전수 검사 (2026-10-02 MASTER QA 3·4·21항): 청약홈 원천 유형(category·kind) → 화면에 나오는 글자를 공고 전부에 대해 대조한다.
// 기대값은 화면 코드가 아니라 원천 값에서 정한 표(EXPECT)로 정한다. 읽기만 하고 아무것도 고치지 않는다.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/supply_type.cjs  → 표준 출력 요약 + evidence/qa/supply-type.json, 위반 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
// 원천 유형 → 화면에 '반드시 있어야 할 말' / '있으면 안 되는 말' (청약홈 분양정보 API: 일반분양 상세 HOUSE_SECD_NM, 무순위·잔여세대 상세 HOUSE_SECD_NM)
const EXPECT = {
  '무순위':          { must: [/무순위/], never: [/재공급/, /불법/] },
  '불법행위 재공급': { must: [/재공급/], never: [/(^|[^·\s])\s*무순위(?!·재공급)/] },
  '신혼희망타운':    { must: [/신혼희망타운/], never: [/무순위/, /재공급/] },
  'APT':             { must: [], never: [/무순위/, /재공급/] },
};
const srcType = x => x.category === 'remainder' ? (x.supply_type || x.kind) : (/신혼희망타운/.test(x.kind || x.supply_type || '') ? '신혼희망타운' : 'APT');
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage({ viewport: { width: 390, height: 844 } });
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  // 1) 지금 공고: 목록 카드 · 상세(일반공급 칸 이름 포함)
  const live = await page.evaluate(() => LISTINGS.map(L => {
    const card = document.createElement('div'); card.innerHTML = listingCard(L, grade(L));
    S.view = 'detail'; S.id = L.id; let det = ''; try { render(); det = document.querySelector('main, #app, body').innerText; } catch (e) { det = 'ERROR ' + e.message; }
    return { id: L.id, name: L.name, category: L.category, kind: L.kind, supply_type: L.supplyType, card: card.innerText.replace(/\s+/g, ' '), badges: (card.querySelector('.badges, .cbadges') || card).innerText.replace(/\s+/g, ' '), genLabel: genLabel(L), detHead: det.slice(0, 600).replace(/\s+/g, ' ') };
  }));
  // 2) 지난 공고 카드 (보관함 전체)
  const arc = JSON.parse(readFileSync(join(DOCS, 'archive/past.json'), 'utf8'));
  const past = await page.evaluate(items => { PAST = { meta: { built: '' }, items }; const out = [];
    pastGroups().forEach(gr => { out.push({ id: gr.no, name: gr.name, category: gr.cat, kind: gr.kind, line: `${gr.cat === 'remainder' ? gr.kind || '무순위' : gr.kind === '신혼희망타운' ? '신혼희망타운' : '일반분양'}` }); });
    return out; }, arc.items);
  await b.close();
  const res = [], bad = [];
  const check = (where, x, text) => {
    const t = srcType(x), e = EXPECT[t];
    if (!e) { res.push([where, x.id, t, 'NOT_TESTABLE', '표에 없는 원천 유형']); return; }
    const miss = e.must.filter(r => !r.test(text)).map(String), hit = e.never.filter(r => r.test(text)).map(String);
    const st = miss.length || hit.length ? 'FAIL' : 'PASS';
    res.push([where, x.id, t, st, st === 'FAIL' ? `없어야 할 말 ${hit} · 있어야 할 말 없음 ${miss} | ${text.slice(0, 160)}` : '']);
    if (st === 'FAIL') bad.push(res[res.length - 1]);
  };
  for (const x of live) {
    check('목록 카드', { ...x, supply_type: x.supply_type }, x.card);
    check('일반공급 칸 이름', x, x.genLabel);
  }
  for (const x of past) check('지난 공고 카드', { ...x, supply_type: x.kind }, x.line);
  const tally = {}; res.forEach(([w, , t, st]) => { const k = w + ' · ' + t; tally[k] = tally[k] || {}; tally[k][st] = (tally[k][st] || 0) + 1; });
  console.log(JSON.stringify(tally, null, 1));
  bad.slice(0, 20).forEach(r => console.log('FAIL', r.join(' | ')));
  writeFileSync(join(ROOT, 'evidence/qa/supply-type.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), tally, fails: bad }, null, 1) + '\n');
  const n = res.length;
  console.log(`[QA 공급유형] 원천 유형 → 화면 글자 ${n}곳 검사 · 위반 ${bad.length}건`);
  process.exit(bad.length ? 1 : 0);
})();
