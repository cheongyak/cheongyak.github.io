// 기능 ai_read 화면 검사 (2026-11-11): AI 가 읽어 채운 공고(terms.ai)는 '신청 가능해 보여요'가 아니라 '확인 필요'까지만 보이고,
// 스위치(config features.ai_read)를 끄면 채우기 전 값(terms_pre_ai)으로 돌아가 '공고문에서 읽지 못함'으로 보이는지 본다.
// 지금 docs/lh-rental.json 에서 조건을 다 채운 사람에게 '가능'이 나오는 공공임대 공고 하나를 골라 그 공고를 AI 가 읽은 것처럼 바꿔 넣는다.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/ai_read_screen.cjs
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const DOCS = join(__dirname, '../../docs');
const SIDO = { '서울특별시': '서울', '부산광역시': '부산', '대구광역시': '대구', '인천광역시': '인천', '광주광역시': '광주', '대전광역시': '대전', '울산광역시': '울산', '세종특별자치시': '세종', '경기도': '경기',
  '강원특별자치도': '강원', '충청북도': '충북', '충청남도': '충남', '전북특별자치도': '전북', '전라남도': '전남', '경상북도': '경북', '경상남도': '경남', '제주특별자치도': '제주' };
async function run(b, aiOn, mutate) {
  const page = await b.newPage({ viewport: { width: 390, height: 844 } });
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    let body = readFileSync(f);
    if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = Object.assign({}, c.features, { lh_rental: true, ai_read: aiOn }); body = JSON.stringify(c); }
    if (u.pathname === '/lh-rental.json') { const d = JSON.parse(body); mutate(d); body = JSON.stringify(d); }
    r.fulfill({ status: 200, body, contentType: { '.html': 'text/html', '.json': 'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
  await page.evaluate(() => new Promise(res => { loadRental(); const t = setInterval(() => { if (RENTAL) { clearInterval(t); res(); } }, 50); }));
  const out = await page.evaluate(SIDO => {
    const N = RENTAL.notices.find(x => x._probe);
    const sido = (N.terms.regions || [])[0] || SIDO[N.region] || '서울';
    const p = Object.assign({}, DEFAULT_PROFILE, { birth: '1985-05-01', married: false, selfOwn: false, spouseOwn: false, household: 'head', parentsOwn: false, hhHomes: '0', eldersOnDeed: 0, kidsOnDeed: 0,
      acctType: 'all', acctSince: '2010-01-01', acctCount: 120, hhSize: 1, kidsMinor: 0, hhIncomeYear: 2000, income: 2000, spouseIncome: 0, assetTotal: 1000, carValue: 0, homeSido: sido, homeSigun: '' });
    const J = rentalJudge(N, p);
    return { id: N.id, s: J.s, items: J.groups.flatMap(g => g.items.map(i => i.s + ' ' + i.t)), crit: (typeof rAiFields === 'function') ? rAiFields(N.terms) : null, account: N.terms.account };
  }, SIDO);
  await page.close();
  return Object.assign(out, { errs });
}
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const pick = d => d.notices.find(N => N.type === '공공임대' && N.judge_type && N.terms && N.terms.account && N.terms.account !== 'none' && (N.terms.regions || []).length && !N.terms.ai
    && (N.terms.groups || []).length === 1 && N.terms.groups[0].income_pct === 'excluded');
  const plain = d => { const N = pick(d); if (N) N._probe = true; };
  const asAi = d => { const N = pick(d); if (!N) return; N._probe = true; const pre = JSON.parse(JSON.stringify(N.terms)); pre.account = null;
    N.terms_pre_ai = pre; N.terms.ai = { fields: ['account'], model: 'test', at: 'test' }; };
  const fails = [];
  const base = await run(b, true, plain);
  if (!base.id) { console.log('[AI 판독 화면 검사] 건너뜀 — 지금 데이터에 맞는 공공임대 공고가 없음'); await b.close(); return; }
  const on = await run(b, true, asAi), off = await run(b, false, asAi);
  if (base.s !== 'ok') fails.push('기준 공고가 가능이 아님: ' + base.s + ' ' + base.items.filter(x => !x.startsWith('ok')).join(' / '));
  if (on.s !== 'check') fails.push('AI 가 읽은 공고가 확인 필요가 아님: ' + on.s);
  if (!on.items.some(x => x.startsWith('check AI가 읽은 기준(청약통장)'))) fails.push('AI 안내 항목이 없음');
  if ((on.crit || []).join() !== '청약통장') fails.push('기준 칸 이름: ' + on.crit);
  if (off.account !== null) fails.push('스위치를 껐는데 AI 값이 남음');
  if (!off.items.some(x => x.includes('청약통장 요건을 공고문에서 읽지 못함'))) fails.push('스위치를 끄면 못 읽음으로 보여야 함');
  if (off.items.some(x => x.includes('AI가 읽은'))) fails.push('스위치를 껐는데 AI 안내가 보임');
  for (const r of [base, on, off]) if (r.errs.length) fails.push('화면 오류 ' + r.errs[0]);
  console.log(`[AI 판독 화면 검사] 공고 ${base.id} · 평소 ${base.s} · AI 가 읽음 ${on.s} · 스위치 끔 ${off.s} · 실패 ${fails.length}` + (fails.length ? '\n  ' + fails.join('\n  ') : ''));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})();
