// 청약봇 화면 검사 (기능: chatbot): 브라우저 화면 → 실제 청약봇 서버 코드(chat/worker/src, AI 대신 고정 문구 답 또는 미리 쓴 답) → 화면까지 끝에서 끝으로.
// 확인: 스위치를 끄면 버튼·방침 문구가 없음 / 켜면 버튼 → 동의 → 질문 → 답의 판정 = 화면 판정 / 미리보기 코드 / 하루 2건 제한·되물음 / 평가 7가지·'정보가 틀렸어요' 다시 판정 /
//       서버 답의 판정이 화면과 다르면 화면이 막음 / 개인정보 가림 / 390px 넘침 없음 / 화면 오류 0.
// 사용: NODE_PATH=... node tools/qa/chatflow.cjs [공고 수(기본 40)] [스크린샷 폴더]
const { chromium } = require('playwright'); const { readFileSync, existsSync } = require('node:fs'); const { join, extname, resolve } = require('node:path');
const ROOT = resolve(__dirname, '..', '..'), DOCS = join(ROOT, 'docs'), N = +process.argv[2] || 40, SHOTS = process.argv[3] || '';
class MemKV { constructor() { this.m = new Map(); } async get(k) { return this.m.get(k) ?? null; } async put(k, v) { this.m.set(k, v); } async delete(k) { this.m.delete(k); } }
(async () => {
  const W = await import(join(ROOT, 'chat/worker/src/index.js'));
  const fails = [], tally = {}; const t = (k, ok, info) => { tally[k] = tally[k] || [0, 0]; tally[k][ok ? 0 : 1]++; if (!ok && fails.length < 30) fails.push(k + ' ' + (info || '')); };
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  async function page(cfgPatch, server, scheme = 'light') {
    const p = await b.newPage({ viewport: { width: 390, height: 844 }, colorScheme: scheme }); const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.route('**/*', async r => { const u = new URL(r.request().url());
      if (u.hostname === 'chat.local') {
        if (r.request().method() === 'OPTIONS') return r.fulfill({ status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'POST' } });
        const out = await server(u.pathname, JSON.parse(r.request().postData() || '{}'));
        return r.fulfill({ status: out.status, body: JSON.stringify(out.body), headers: { 'access-control-allow-origin': '*', 'content-type': 'application/json' } }); }
      if (u.hostname !== 'j.local') return r.abort();
      const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
      if (u.pathname === '/config.json') { const c = JSON.parse(readFileSync(f, 'utf8')); Object.assign(c, cfgPatch.top || {}); Object.assign(c.features, cfgPatch.features || {}); return r.fulfill({ status: 200, body: JSON.stringify(c), contentType: 'application/json' }); }
      if (!existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: readFileSync(f), contentType: extname(f) === '.html' ? 'text/html' : 'application/json' }); });
    await p.goto('http://j.local/' + (cfgPatch.query || ''), { waitUntil: 'networkidle' }); await p.waitForTimeout(500);
    return { p, errs };
  }
  // 실제 서버 코드 + 메모리 KV + 공고별 근거 파일
  const mkServer = (env, opts = {}) => { const kv = new MemKV(); const calls = []; return { kv, calls, fn: async (path, body) => {
    calls.push({ path, body });
    if (path === '/feedback') return W.handleFeedback(env, body, { kv });
    const nid = String(body.engine && body.engine.listing && body.engine.listing.id || '').split('-')[0];
    const fetchImpl = async () => existsSync(join(DOCS, 'chat-evidence', nid + '.json')) ? { ok: true, json: async () => JSON.parse(readFileSync(join(DOCS, 'chat-evidence', nid + '.json'), 'utf8')) } : { ok: false };
    const r = await W.handleChat(env, { ...body, ip: '10.0.0.1' }, { kv, fetch: fetchImpl, llm: opts.llm });
    calls[calls.length - 1].follow_up = r.body && r.body.follow_up;
    if (opts.tamper && r.body.kind === 'answer') { r.body.verdict = r.body.answer.verdict = r.body.verdict === '가능' ? '불가' : '가능'; }
    if (r.body) delete r.body.log; return r; } }; };
  const PROFS = [
    { homeSido: '경기', homeSigun: '광명시', household: 'head', selfOwn: false, married: true, acctType: 'all', acctSince: '2015-03-01', acctAmount: 1500, acctCount: 100, hhHomes: '0', everWin: 'none', income: 5000, hhSize: 2, marriedOn: '2022-05-01' },
    { homeSido: '서울', household: 'parents', parents60: true, parentsOwn: true, selfOwn: false, married: false, acctType: '' },
    { homeSido: '인천', household: 'head', selfOwn: true, hhHomes: '1', married: false, acctType: 'all', acctSince: '2010-01-01', acctAmount: 300, everWin: 'none' },
  ];
  const setProfile = (p, pr) => p.evaluate(pr => { localStorage.setItem('cy-profile', JSON.stringify(pr)); S.profile = Object.assign({}, DEFAULT_PROFILE, pr); syncHome(S.profile); }, pr);

  // 1) 스위치 꺼짐 (지금 설정 그대로): 버튼 없음, 방침에 청약봇 문구 없음 (시행 전 예고의 '바뀐 뒤 전문' 안은 제외)
  { const { p, errs } = await page({ top: { chat_api: 'https://chat.local' } }, async () => ({ status: 500, body: {} }));
    await setProfile(p, PROFS[0]);
    const r = await p.evaluate(() => { const ids = LISTINGS.filter(x => !x.sample).slice(0, 20).map(x => x.id); let btn = 0; for (const id of ids) { S.id = id; go('detail'); if (document.querySelector('[data-chat="open"]')) btn++; }
      go('privacy'); const cur = [...document.querySelectorAll('#app > section, #app > p')].filter(x => !x.closest('.legalnote')).map(x => x.textContent).join(' ');
      return { btn, anth: cur.includes('Anthropic') }; });
    t('꺼짐: 버튼 없음', r.btn === 0, JSON.stringify(r)); t('꺼짐: 시행 중 방침에 청약봇 없음', !r.anth); t('꺼짐: 화면 오류 0', !errs.length, errs[0]); await p.close(); }

  // 2) 켜짐: 공고 N개 × 프로필 3개 — 버튼 → 동의 → 빠른 질문 → 답 판정 = 화면 판정
  const srv = mkServer({ CHAT_OPEN: '1' });
  for (const scheme of ['light', 'dark']) {
    const { p, errs } = await page({ top: { chat_api: 'https://chat.local' }, features: { chatbot: true } }, srv.fn, scheme);
    const ids = await p.evaluate(n => LISTINGS.filter(x => !x.sample).slice(0, n).map(x => x.id), scheme === 'light' ? N : 6);
    let first = true;
    for (const pr of scheme === 'light' ? PROFS : PROFS.slice(0, 1)) { await setProfile(p, pr);
      for (const id of ids) {
        srv.kv.m.clear();   // 하루 제한은 따로 검사
        await p.evaluate(id => { S.id = id; go('detail'); }, id);
        const btn = await p.$('[data-chat="open"]'); t('켜짐: 버튼 있음', !!btn, id); if (!btn) continue;
        await btn.click();
        if (first) { t('동의 화면 먼저', !!(await p.$('[data-chat="consent"]'))); if (SHOTS) await p.screenshot({ path: `${SHOTS}/chat-consent-${scheme}.png` }); await p.click('[data-chat="consent"]'); first = false; }
        await p.click('[data-chat="quick"]');
        await p.waitForSelector('.chatans, .chatbot-msg:not(.chatwait)', { timeout: 8000 }).catch(() => {});
        const r = await p.evaluate(id => { const shown = (document.querySelector('.chatverdict b') || {}).textContent || '', v = cpExplain(id, S.profile).verdict;
          const want = { '가능': '신청 가능', '불가': '신청 불가', '확인 필요': '확인 필요', '2순위만': '2순위만 가능' }[v];
          const panel = document.querySelector('.chatpanel'); return { shown, want, v, over: panel ? panel.scrollWidth > panel.clientWidth + 1 : true, pw: panel && [panel.scrollWidth, panel.clientWidth], docOver: document.documentElement.scrollWidth > innerWidth, dw: [document.documentElement.scrollWidth, innerWidth] }; }, id);
        t('답 판정 = 화면 판정', r.shown === r.want, id + ' ' + JSON.stringify(r)); t('대화창 넘침 없음', !r.over && !r.docOver, id + ' ' + JSON.stringify(r));
        if (SHOTS && id === ids[0] && pr === PROFS[0]) await p.screenshot({ path: `${SHOTS}/chat-answer-${scheme}.png` });
        await p.click('.chatx'); t('닫으면 사라짐', !(await p.$('#chatsheet')));
      } }
    t('켜짐: 화면 오류 0 (' + scheme + ')', !errs.length, errs[0]); await p.close();
  }
  // 3) 하루 2건 · 되물음은 세지 않음 · 개인정보 가림 · 평가 · '정보가 틀렸어요'
  { const s3 = mkServer({ CHAT_OPEN: '1' }); const { p, errs } = await page({ top: { chat_api: 'https://chat.local' }, features: { chatbot: true } }, s3.fn);
    await setProfile(p, PROFS[1]);   // 세대원 → 확인 필요·되물음이 나오기 쉬운 프로필
    const id = await p.evaluate(() => LISTINGS.filter(x => !x.sample)[0].id);
    await p.evaluate(id => { localStorage.setItem('cy-chat-consent', CONFIG.chat_legal_date || 'preview'); S.id = id; go('detail'); }, id);
    const ask = async q => { await p.fill('#chatq', q); await p.click('.chatform button'); await p.waitForFunction(() => CHAT && !CHAT.busy, null, { timeout: 8000 }); };
    await p.click('[data-chat="open"]');
    await ask('제 번호 010-1234-5678 인데 저 신청 가능해요?');
    const sent = s3.calls.filter(c => c.path === '/chat').pop().body.question;
    t('개인정보: 보내기 전에 가림', !sent.includes('5678') && sent.includes('[전화번호 가림]'), sent);
    t('개인정보: 가렸다고 알림', !!(await p.$('.chatme .small')));
    const asked = await p.evaluate(() => { const m = [...CHAT.msgs].reverse().find(x => x.ans); return !!(m && m.ans.ask); });
    if (asked) { await ask('네 세대주예요'); t('되물음 답은 세지 않음', s3.calls.filter(c => c.path === '/chat').pop().follow_up === true); }
    await p.click('.chatx'); await p.click('[data-chat="open"]');
    await ask('필요한 서류는 뭐야?');
    t('두 번째 질문 뒤 남은 횟수 0', (await p.evaluate(() => CHAT.remaining)) === 0);
    await p.click('.chatx'); await p.click('[data-chat="open"]');
    await ask('접수 일정 알려줘');
    const lim = await p.evaluate(() => CHAT.msgs[CHAT.msgs.length - 1].text || '');
    t('하루 2건 넘으면 안내', /2건|모두 쓰셨/.test(lim), lim);
    // 평가: 새 창에서 1건(제한 풀고)
    s3.kv.m.clear(); await p.click('.chatx'); await p.click('[data-chat="open"]'); await ask('왜 이 판정이 나왔어?');
    await p.click('[data-chat="down"]'); t('👎 이유 7가지', (await p.$$('[data-chat="reason"]')).length === 7);
    await p.click('[data-chat="reason"][data-v="wrong_info"]');
    const fb = await p.evaluate(() => (document.querySelector('.chatfbdone') || {}).textContent || '');
    t("'정보가 틀렸어요' → 다시 판정해 같음", /다시 판정해도 같아요/.test(fb), fb);
    const fbCall = s3.calls.filter(c => c.path === '/feedback').pop();
    t('평가는 이유·재판정 결과만 보냄', fbCall && JSON.stringify(Object.keys(fbCall.body).sort()) === '["reason","recheck","vote"]', fbCall && JSON.stringify(fbCall.body));
    const kvDump = [...s3.kv.m.entries()].map(([k, v]) => k + v).join(' ');
    t('서버 저장소에 질문·전화번호·IP 없음', !/5678|신청 가능해요|10\.0\.0\.1/.test(kvDump), kvDump.slice(0, 200));
    t('평가·제한 화면 오류 0', !errs.length, errs[0]); await p.close(); }
  // 4) 서버가 판정을 뒤집어 보내도 화면이 막음
  { const s4 = mkServer({ CHAT_OPEN: '1' }, { tamper: true }); const { p, errs } = await page({ top: { chat_api: 'https://chat.local' }, features: { chatbot: true } }, s4.fn);
    await setProfile(p, PROFS[0]); const id = await p.evaluate(() => LISTINGS.filter(x => !x.sample)[0].id);
    await p.evaluate(id => { localStorage.setItem('cy-chat-consent', CONFIG.chat_legal_date || 'preview'); S.id = id; go('detail'); }, id);
    await p.click('[data-chat="open"]'); await p.click('[data-chat="quick"]'); await p.waitForFunction(() => CHAT && !CHAT.busy);
    t('뒤집힌 판정은 보여주지 않음', !(await p.$('.chatans')) && /보여 드리지 않았어요/.test(await p.evaluate(() => CHAT.msgs[CHAT.msgs.length - 1].text || '')));
    t('변조 검사 화면 오류 0', !errs.length, errs[0]); await p.close(); }
  // 5) 미리보기: 스위치 꺼짐 + ?chat=preview → 코드 입력 → 서버가 코드 확인
  { const s5 = mkServer({ CHAT_PREVIEW_CODE: 'code-abc-123' }); const { p, errs } = await page({ top: { chat_api: 'https://chat.local' }, query: '?chat=preview' }, s5.fn);
    await setProfile(p, PROFS[0]); const id = await p.evaluate(() => LISTINGS.filter(x => !x.sample)[0].id);
    await p.evaluate(id => { S.id = id; go('detail'); }, id);
    t('미리보기: 버튼 있음', !!(await p.$('[data-chat="open"]')));
    await p.click('[data-chat="open"]'); t('미리보기: 코드 먼저', !!(await p.$('#chatcode')));
    await p.fill('#chatcode', 'wrong'); await p.click('[data-chat="code"]'); await p.click('[data-chat="consent"]'); await p.click('[data-chat="quick"]'); await p.waitForFunction(() => CHAT && !CHAT.busy);
    t('미리보기: 틀린 코드는 거절', /코드가 맞지 않아요/.test(await p.evaluate(() => CHAT.msgs[CHAT.msgs.length - 1].text || '')));
    await p.click('.chatx'); await p.click('[data-chat="open"]'); await p.fill('#chatcode', 'code-abc-123'); await p.click('[data-chat="code"]');
    await p.click('[data-chat="quick"]'); await p.waitForFunction(() => CHAT && !CHAT.busy);
    t('미리보기: 맞는 코드면 답함', !!(await p.$('.chatans')));
    await p.goto('http://j.local/?chat=off', { waitUntil: 'networkidle' }); await p.waitForTimeout(300); await p.evaluate(id => { S.id = id; go('detail'); }, id);
    t('미리보기 해제(?chat=off)', !(await p.$('[data-chat="open"]')));
    t('미리보기 화면 오류 0', !errs.length, errs[0]); await p.close(); }
  // 6) 운영자 명령: 미리보기 코드로 !점검 → 점검 안내, !오픈 → 다시 답함 (2026-10-02)
  { const s6 = mkServer({ CHAT_PREVIEW_CODE: 'code-abc-123' }); const { p, errs } = await page({ top: { chat_api: 'https://chat.local' }, query: '?chat=preview' }, s6.fn);
    await setProfile(p, PROFS[0]); const id = await p.evaluate(() => LISTINGS.filter(x => !x.sample)[0].id);
    await p.evaluate(id => { localStorage.setItem('cy-chat-code', 'code-abc-123'); localStorage.setItem('cy-chat-consent', CONFIG.chat_legal_date || 'preview'); S.id = id; go('detail'); }, id);
    await p.click('[data-chat="open"]');
    const ask = async q => { await p.fill('#chatq', q); await p.click('.chatform button'); await p.waitForFunction(() => CHAT && !CHAT.busy, null, { timeout: 8000 }); return p.evaluate(() => CHAT.msgs[CHAT.msgs.length - 1].text || (CHAT.msgs[CHAT.msgs.length - 1].ans ? 'ANSWER' : '')); };
    t('!점검 → 운영자 명령 안내', /운영자 명령 · 점검 모드/.test(await ask('!점검')));
    t('점검 중 질문 → 점검 안내', /점검 중/.test(await ask('접수 일정 알려줘')));
    t('!오픈 → 켰어요', /켰어요/.test(await ask('!오픈')));
    t('!오픈 뒤 답함', (await ask('왜 이 판정이 나왔어?')) === 'ANSWER');
    t('운영 명령 화면 오류 0', !errs.length, errs[0]); await p.close(); }
  await b.close();
  const total = Object.values(tally).reduce((a, [o, f]) => a + o + f, 0), bad = Object.values(tally).reduce((a, [, f]) => a + f, 0);
  console.log(`[청약봇 화면 검사] ${total - bad}/${total} 통과`); for (const [k, [o, f]] of Object.entries(tally)) console.log(`  ${f ? '✗' : '✓'} ${k}: ${o}/${o + f}`);
  fails.forEach(f => console.log('    - ' + f)); process.exit(bad ? 1 : 0);
})();
