// 기능 ai_read_sale 화면 검사 (2026-11-11): 규칙이 못 읽은 거주 지역 요건에 AI 참고 내용이 붙어도 **판정은 그대로 '확인 필요'** 인지,
// 참고 내용·근거 문장이 보이는지, 스위치를 끄면 사라지는지, 규칙이 읽은 공고에는 붙지 않는지 본다.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/ai_read_sale_screen.cjs
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const DOCS = join(__dirname, '../../docs');
const HINT = { residence: { text: '해당지역 경기도 시험시 거주자 · 기타지역 서울·인천·경기', quote: '입주자 모집공고일 현재 경기도 시험시 거주자 <b>' } };
async function run(b, aiOn, unread) {
  const page = await b.newPage({ viewport: { width: 390, height: 844 } });
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    let body = readFileSync(f);
    if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = Object.assign({}, c.features, { ai_read_sale: aiOn }); body = JSON.stringify(c); }
    if (u.pathname === '/listings.json') { const d = JSON.parse(body); const x = d.find(y => y.residence && y.residence.area); x._probe = true; x.notice_ai = HINT; if (unread) x.residence = null; body = JSON.stringify(d); }
    r.fulfill({ status: 200, body, contentType: { '.html': 'text/html', '.json': 'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => typeof LISTINGS !== 'undefined' && LISTINGS.length > 0, null, { timeout: 20000 });
  const out = await page.evaluate(() => {
    const id = Object.keys(NOTICE_AI)[0], L = LISTINGS.find(x => x.id === id);
    const p = Object.assign({}, DEFAULT_PROFILE, { homeSido: L.sido, homeSigun: '' });
    const it = residenceItem(L, p);
    return { id, s: it.s, v: it.v, note: it.note, hint: aiHintHtml(L, 'residence'), hasRes: !!L.residence };
  });
  await page.close();
  return Object.assign(out, { errs });
}
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const on = await run(b, true, true), off = await run(b, false, true), read = await run(b, true, false);
  const fails = [];
  if (on.s !== 'warn') fails.push('못 읽은 거주 요건 판정이 확인 필요(warn)가 아님: ' + on.s);
  if (!/AI가 공고문에서 읽은 내용\(참고 — 판정에는 쓰지 않았어요\): 해당지역 경기도 시험시 거주자/.test(on.hint)) fails.push('참고 내용이 안 보임');
  if (!on.hint.includes('&lt;b&gt;') || on.hint.includes('거주자 <b>')) fails.push('근거 문장이 그대로(HTML 로) 들어감');
  if (/AI가/.test(on.note || '')) fails.push('판정 함수의 안내문이 바뀜(판정 함수는 건드리지 않아야 함)');
  if (off.hint !== '') fails.push('스위치를 껐는데 참고 내용이 보임');
  if (off.s !== on.s || off.v !== on.v) fails.push('스위치에 따라 판정이 달라짐');
  if (!read.hasRes || read.s === undefined) fails.push('기준 공고 없음');
  for (const r of [on, off, read]) if (r.errs.length) fails.push('화면 오류 ' + r.errs[0]);
  console.log(`[AI 판독 화면 검사·분양] 공고 ${on.id} · 못 읽음+AI 참고 → 판정 '${on.v}' · 스위치 끔 → 참고 ${off.hint ? '보임' : '없음'} · 실패 ${fails.length}` + (fails.length ? '\n  ' + fails.join('\n  ') : ''));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})();
