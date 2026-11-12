// 기능 ai_read_sh 화면 검사 (2026-11-12): 규칙이 자격을 못 읽은 SH 공고에 세션이 읽은 참고 내용(N.notice_ai)이 붙어도 **판정은 그대로**인지,
// 참고 내용·근거 문장이 상세 화면에 보이는지(HTML 로 들어가지 않는지), 스위치를 끄면 사라지는지 본다.
// docs/sh-rental.json 의 SH 공고 하나를 '자격 못 읽음(terms 없음) + 참고 내용'으로 바꿔 넣는다.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/ai_read_sh_screen.cjs
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const DOCS = join(__dirname, '../../docs');
const AI = { groups: [{ name: '시험계층 <b>', items: [{ k: 'homeless', label: '무주택', text: '세대원 전원 무주택(무주택세대구성원)', quote: '서울시에 거주하는 무주택 세대 구성원 <i>' }, { k: 'income_pct', label: '소득', text: '70% 이하', quote: '도시근로자 월평균 소득 70% 이하' }] }], need: ['자격'], model: 'test', at: 'test' };
const KST = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10), FUT = new Date(Date.now() + 9 * 3600e3 + 5 * 864e5).toISOString().slice(0, 10);
async function run(b, aiOn, withAi) {
  const page = await b.newPage({ viewport: { width: 390, height: 844 } });
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    let body = readFileSync(f);
    if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = Object.assign({}, c.features, { lh_rental: true, sh_rental: true, sh_judge: true, ai_read_sh: aiOn }); body = JSON.stringify(c); }
    if (u.pathname === '/sh-rental.json') { const d = JSON.parse(body); const N = d.notices[0]; N._probe = true; N.terms = null; N.judge_type = false; N.close = FUT; delete N.notice_ai;
      N.schedule = [{ complex: null, apply_start: KST, apply_end: FUT, docs_target: null, winner: null, rank1: false, quote: '' }]; if (withAi) N.notice_ai = AI; body = JSON.stringify(d); }
    r.fulfill({ status: 200, body, contentType: { '.html': 'text/html', '.json': 'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
  await page.evaluate(() => new Promise(res => { loadRental(); const t = setInterval(() => { if (RENTAL && RENTAL.notices.some(x => x._probe)) { clearInterval(t); res(); } }, 50); setTimeout(res, 15000); }));
  const out = await page.evaluate(() => {
    const N = RENTAL.notices.find(x => x._probe); if (!N) return { id: null };
    const J = rentalJudge(N, Object.assign({}, DEFAULT_PROFILE, { birth: '1995-03-01', hhSize: 1, hhIncomeYear: 3000, income: 3000, homeSido: '서울' }));
    S.rid = N.id; let html = ''; try { html = vRDetail(); } catch (e) { html = 'ERR ' + e.message; }
    return { id: N.id, s: J.s, groups: J.groups.length, block: shAiHtml(N), inDetail: html.includes('AI가 공고문에서 읽은 자격 기준'), err: html.startsWith('ERR') ? html : '' };
  });
  await page.close();
  return Object.assign(out, { errs });
}
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const on = await run(b, true, true), off = await run(b, false, true), none = await run(b, true, false);
  const fails = [];
  if (!on.id) fails.push('SH 공고를 화면에서 찾지 못함');
  else {
    if (on.s !== none.s || on.groups !== none.groups || on.s !== off.s) fails.push(`참고 내용에 따라 판정이 달라짐: 참고 있음 ${on.s} · 없음 ${none.s} · 스위치 끔 ${off.s}`);
    if (on.s !== 'unsupported') fails.push('자격을 못 읽은 SH 공고 판정이 판정 미지원이 아님: ' + on.s);
    if (!/판정에는 쓰지 않았어요/.test(on.block) || !on.block.includes('소득: 70% 이하') || !on.block.includes('출처: 모집공고문 · AI 판독')) fails.push('참고 내용·출처가 안 보임');
    if (!on.block.includes('&lt;b&gt;') || !on.block.includes('&lt;i&gt;') || /<b>\s*<\/div>|구성원 <i>/.test(on.block)) fails.push('계층 이름·근거 문장이 그대로(HTML 로) 들어감');
    if (!on.inDetail) fails.push('상세 화면에 참고 내용이 없음 ' + on.err);
    if (off.block !== '' || off.inDetail) fails.push('스위치를 껐는데 참고 내용이 보임');
    if (none.block !== '' || none.inDetail) fails.push('참고 내용이 없는 공고에 블록이 보임');
  }
  for (const r of [on, off, none]) if (r.errs.length) fails.push('화면 오류 ' + r.errs[0]);
  console.log(`[AI 판독 화면 검사·SH] 공고 ${on.id} · 참고 내용 있음 → 판정 '${on.s}' 그대로 · 스위치 끔 → 참고 ${off.block ? '보임' : '없음'} · 실패 ${fails.length}` + (fails.length ? '\n  ' + fails.join('\n  ') : ''));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})();
