// 검색·필터 일치 검사 (2026-10-02 MASTER QA 23항): 화면 필터(matches)의 결과가 수집 원자료(docs/listings.json)로 따로 계산한 기대 집합과 같은지
// 단일 필터 전부 + 무작위 조합 200개(시드 고정)를 본다. 기대값은 원자료 필드(sido·supply_type·house_dtl·rent_secd·special_apply·price·area·날짜)로 계산하고 화면 함수는 쓰지 않는다.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/filter_check.cjs → evidence/qa/filter-check.json, 다르면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
let seed = 20261002; const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
(async () => {
  const raw = (j => j.listings || j)(JSON.parse(readFileSync(join(DOCS, 'listings.json'), 'utf8')));
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage();
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(400);
  const today = await page.evaluate(() => TODAY);
  // 원자료로 정한 기대 (공고 단위가 아니라 주택형 단위)
  const status = x => { const s = x.special_apply || x.apply, e = x.apply_end || x.apply; return s && today < s ? '접수 예정' : e && today > e ? '마감' : (s || e) ? '접수 중' : ''; };
  const PB = { '5': [0, 5], '5-10': [5, 10], '10-15': [10, 15], '15-20': [15, 20], '20': [20, 1e9] }, SB = { s: [0, 60], m: [60, 85], l: [85, 1e9] };
  const pred = f => x => (!f.sido || x.sido === f.sido) && (!f.supply || (x.supply_type || x.kind) === f.supply) && (!f.dtl || (x.house_dtl || null) === f.dtl)
    && (!f.rent || (x.rent_secd || null) === f.rent) && (!f.special || (f.special === 'yes') === !!x.special_apply) && (!f.status || status(x) === f.status)
    && (!f.price || (x.price != null && x.price >= PB[f.price][0] && x.price < PB[f.price][1])) && (!f.size || (x.area != null && x.area > SB[f.size][0] && x.area <= SB[f.size][1]));
  const vals = { sido: [...new Set(raw.map(x => x.sido))], supply: [...new Set(raw.map(x => x.supply_type || x.kind))], dtl: ['민영', '국민'], rent: [...new Set(raw.map(x => x.rent_secd).filter(Boolean))],
    special: ['yes', 'no'], status: ['접수 예정', '접수 중', '마감'], price: Object.keys(PB), size: Object.keys(SB) };
  const filters = []; for (const [k, vs] of Object.entries(vals)) for (const v of vs) filters.push({ [k]: v });
  for (let i = 0; i < 200; i++) { const f = {}; for (const [k, vs] of Object.entries(vals)) if (rnd() < 0.35) f[k] = vs[Math.floor(rnd() * vs.length)]; filters.push(f); }
  const got = await page.evaluate(fs => fs.map(f => LISTINGS.filter(L => matches(L, Object.assign({}, F0, f))).map(L => L.id).sort()), filters);
  const bad = [];
  filters.forEach((f, i) => { const exp = raw.filter(pred(f)).map(x => x.id).sort(); const g = got[i];
    if (JSON.stringify(exp) !== JSON.stringify(g)) bad.push({ filter: f, missing: exp.filter(x => !g.includes(x)).slice(0, 5), extra: g.filter(x => !exp.includes(x)).slice(0, 5), exp: exp.length, got: g.length }); });
  // 검색어: '서울' 은 서울 공고만, '무순위'는 무순위 유형만, '불법행위'·'재공급'은 재공급 전부
  const sq = await page.evaluate(() => { const r = q => LISTINGS.filter(L => searchHit(L, q)); return { 서울: r('서울').map(L => L.sido), 무순위: r('무순위').map(L => L.supplyType), 재공급: r('재공급').map(L => L.supplyType), 불법행위: r('불법행위').map(L => L.supplyType) }; });
  const nRe = raw.filter(x => (x.supply_type || '') === '불법행위 재공급').length;
  const sbad = [];
  if (sq.서울.some(s => s !== '서울')) sbad.push('서울 검색에 다른 시·도');
  if (sq.무순위.some(s => s !== '무순위')) sbad.push('무순위 검색에 다른 유형: ' + [...new Set(sq.무순위)].join(','));
  if (sq.재공급.length !== nRe || sq.불법행위.length !== nRe) sbad.push(`재공급 검색 ${sq.재공급.length}·불법행위 ${sq.불법행위.length} ≠ 원자료 ${nRe}`);
  await b.close();
  const rep = { date: today, filters: filters.length, filter_fails: bad.length, search_fails: sbad, fails: bad.slice(0, 20) };
  writeFileSync(join(ROOT, 'evidence/qa/filter-check.json'), JSON.stringify(rep, null, 1) + '\n');
  console.log(`[QA 필터] 조합 ${filters.length}개 · 다름 ${bad.length} · 검색 ${sbad.length ? sbad.join(' / ') : '이상 없음'}`);
  bad.slice(0, 5).forEach(x => console.log(JSON.stringify(x)));
  process.exit(bad.length || sbad.length ? 1 : 0);
})();
