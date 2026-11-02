// 청약봇 자유 답변 화면 검사 (기능 bot_free_answer, 2026-11-03): 브라우저 화면 → 실제 청약봇 서버 코드 handleFree(AI 대신 미리 쓴 답) → 화면.
// 확인: ① 청약봇 '광교 … 세대주' 질문 → /free 로 광교 공고 2개(527·528)의 공고 사실을 보내고, 내 조건 값·판정은 보내지 않음 → '청약봇 답' 칸·근거·공고 카드
//       ② 제도 질문 → 공고 없이 /free → 청약 질문 화면 ③ AI 가 계속 막히면 원문 조각 기본 답 화면 ④ 이 공고 물어보기 → /free (공고 1개 + 내 판정 요약) → 말풍선·평가
//       ⑤ 되물음 '이어서 답하기' → 앞 질문·답(history)·같은 공고 ⑥ 스위치 끄면 /free 를 부르지 않음 ⑦ 390px 넘침 없음·화면 오류 0 (밝은·어두운)
// 사용: node tools/qa/free_answer.cjs [스크린샷 폴더]   → evidence/qa/free-answer.json
const { chromium } = require('playwright'); const { readFileSync, existsSync, writeFileSync } = require('node:fs'); const { join, extname, resolve } = require('node:path');
const ROOT = resolve(__dirname, '..', '..'), DOCS = join(ROOT, 'docs'), SHOTS = process.argv[2] || '';
class MemKV { constructor() { this.m = new Map(); } async get(k) { return this.m.get(k) ?? null; } async put(k, v) { this.m.set(k, v); } async delete(k) { this.m.delete(k); } }
(async () => {
  const W = await import(join(ROOT, 'chat/worker/src/index.js'));
  const fails = [], tally = {}; const t = (k, ok, info) => { tally[k] = tally[k] || [0, 0]; tally[k][ok ? 0 : 1]++; if (!ok && fails.length < 30) fails.push(k + ' ' + (info || '')); };
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const fetchImpl = async u => { const f = join(DOCS, new URL(String(u)).pathname.slice(1)); return existsSync(f) ? { ok: true, json: async () => JSON.parse(readFileSync(f, 'utf8')) } : { ok: false }; };
  const mk = (llm) => { const kv = new MemKV(), calls = []; return { kv, calls, fn: async (path, body) => {
    calls.push({ path, body });
    if (path === '/feedback') return W.handleFeedback({}, body, { kv });
    const env = { CHAT_OPEN: '1' };
    const r = path === '/free' ? await W.handleFree(env, { ...body, ip: '10.0.0.2' }, { kv, fetch: fetchImpl, llm, today: '2026-11-03' })
      : await W.handleChat(env, { ...body, ip: '10.0.0.2' }, { kv, fetch: fetchImpl, llm: async () => { throw new Error('qa'); } });
    if (r.body) delete r.body.log; return r; } }; };
  // 미리 쓴 답: 근거 번호 중 실제로 있는 것(N1·P1)을 단다
  const goodLlm = async ({ user }) => { const ids = [...user.matchAll(/"id":"([PNLEF]\d+)"/g)].map(m => m[1]); const ref = ids.filter(i => /^[NP]/.test(i)).slice(0, 2);
    return { text: JSON.stringify({ answer: '공고일 기준으로 판단해요. 공고일 뒤에 세대주가 됐다면 **생애최초·노부모부양 특별공급과 일반공급 1순위**는 신청할 수 없어요' + (ref[0] ? ' [' + ref[0] + ']' : '') + '.\n- 신혼부부·신생아·다자녀 특별공급은 세대주가 아니어도 돼요' + (ref[1] ? ' [' + ref[1] + ']' : '') + '.\n- 일반공급 2순위는 세대주가 아니어도 돼요.\n신청 전 모집공고문과 청약홈에서 꼭 확인하세요.', refs: ref, ask: '세대주가 된 날짜가 정확히 언제인가요?' }) }; };
  const badLlm = async () => ({ text: JSON.stringify({ answer: '로또 청약이니 무조건 넣으세요. 공고일 기준 세대주 요건은 신경 쓰지 않아도 돼요.', refs: [] }) });
  async function page(features, server, scheme = 'light') {
    const p = await b.newPage({ viewport: { width: 390, height: 844 }, colorScheme: scheme }); const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.route('**/*', async r => { const u = new URL(r.request().url());
      if (u.hostname === 'chat.local') {
        if (r.request().method() === 'OPTIONS') return r.fulfill({ status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'POST' } });
        const out = await server(u.pathname, JSON.parse(r.request().postData() || '{}'));
        return r.fulfill({ status: out.status, body: JSON.stringify(out.body), headers: { 'access-control-allow-origin': '*', 'content-type': 'application/json' } }); }
      if (u.hostname !== 'j.local') return r.abort();
      const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
      if (u.pathname === '/config.json') { const c = JSON.parse(readFileSync(f, 'utf8')); c.chat_api = 'https://chat.local'; Object.assign(c.features, features); return r.fulfill({ status: 200, body: JSON.stringify(c), contentType: 'application/json' }); }
      if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
      r.fulfill({ status: 200, body: readFileSync(f), contentType: extname(f) === '.html' ? 'text/html' : /\.m?js$/.test(f) ? 'text/javascript' : 'application/json' }); });
    await p.goto('http://j.local/', { waitUntil: 'networkidle' }); await p.waitForTimeout(400);
    await p.evaluate(() => { localStorage.setItem('cy-chat-consent', CONFIG.chat_legal_date || 'preview'); });
    return { p, errs };
  }
  const PROF = { homeSido: '경기', homeSigun: '수원시', household: 'head', selfOwn: false, married: true, acctType: 'all', acctSince: '2015-03-01', acctAmount: 1500, acctCount: 100, hhHomes: '0', everWin: 'none', income: 7777 };
  const setProfile = (p, pr) => p.evaluate(pr => { localStorage.setItem('cy-profile', JSON.stringify(pr)); S.profile = Object.assign({}, DEFAULT_PROFILE, pr); syncHome(S.profile); }, pr);
  const botAsk = async (p, q) => { await p.evaluate(() => { BOT.cur = null; go('bot'); }); await p.fill('#botq', q); await p.click('[data-action="bot-go"]'); await p.waitForFunction(() => !BOT.busy, null, { timeout: 20000 }); await p.waitForTimeout(150); };
  const overflow = p => p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  const Q = '어제 세대주 됐는데 광교 자연앤센트레빌 쓸 수 있어?';
  const has528 = await (async () => { try { const L = JSON.parse(readFileSync(join(DOCS, 'listings.json'), 'utf8')); return (Array.isArray(L) ? L : L.listings || []).some(x => /^2026000528-/.test(x.id)); } catch (e) { return false; } })();

  for (const scheme of ['light', 'dark']) {
    // ① 청약봇 공고 질문
    const s1 = mk(goodLlm); const { p, errs } = await page({ bot_free_answer: true, bot_find_ai: true, bot_find: true }, s1.fn, scheme);
    await setProfile(p, PROF);
    if (has528) {
      await botAsk(p, Q);
      const fr = s1.calls.filter(c => c.path === '/free'), v2 = s1.calls.filter(c => c.path === '/v2/llm');
      const body = fr[0] && fr[0].body, ids = body ? body.listings.map(x => x.id.split('-')[0]) : [];
      t('① /free 한 번 부름 (V2 AI 설명은 안 부름)', fr.length === 1 && v2.length === 0, JSON.stringify({ free: fr.length, v2: v2.length }));
      t('① 광교 공고(528) 사실을 보냄', ids.includes('2026000528'), JSON.stringify(ids));
      t('① 공고 사실에 공고일·규제지역·세대주 요건·접수일', !!(body && body.listings.some(x => Object.keys(x.facts).some(k => /^공고일/.test(k)) && x.facts['규제지역'] && x.facts['일반공급 1순위 세대주 요건'] && x.facts['특별공급 접수'] && x.facts['모집공고문'])), body && JSON.stringify(body.listings[0].facts).slice(0, 200));
      t('① 내 조건 값·판정은 안 보냄', !!body && !JSON.stringify(body).includes('7777') && !body.engine && !/내 자격/.test(body.find || ''), body && (body.find || '').slice(0, 120));
      const ui = await p.evaluate(() => ({ card: !!document.querySelector('.freecard .freeans'), txt: (document.querySelector('.freecard') || {}).textContent || '', refs: document.querySelectorAll('.freecard .chatsrc li').length, cards: document.querySelectorAll('.botg .card, .botg article, .botg [data-open]').length, follow: !!document.querySelector('[data-action="bot-follow"]') }));
      t('① 청약봇 답 칸', ui.card && /세대주/.test(ui.txt), ui.txt.slice(0, 80));
      t('① 근거 목록', ui.refs >= 1, String(ui.refs)); t('① 공고 카드도 그대로', ui.cards >= 1, String(ui.cards)); t('① 되물음 이어서 답하기 버튼', ui.follow);
      if (SHOTS) await p.screenshot({ path: `${SHOTS}/free-bot-${scheme}.png`, fullPage: true });
      t('① 390px 넘침 없음', !(await overflow(p)));
      // ⑤ 이어서 답하기
      if (ui.follow) { await p.click('[data-action="bot-follow"]'); await p.fill('#botq', '11월 2일이요'); await p.click('[data-action="bot-go"]'); await p.waitForFunction(() => !BOT.busy, null, { timeout: 20000 });
        const f2 = s1.calls.filter(c => c.path === '/free').pop().body;
        t('⑤ 이어서: 앞 질문·답 history', (f2.history || []).length === 2 && f2.history[0].text === Q, JSON.stringify(f2.history || []).slice(0, 120));
        t('⑤ 이어서: 같은 공고·같은 대화', f2.listings.some(x => /^2026000528-/.test(x.id)) && f2.conversation_id === body.conversation_id);
        t('⑤ 이어서: 답 화면', await p.evaluate(() => !!(BOT.cur && BOT.cur.mode === 'free' && BOT.cur.free))); }
    } else t('① 광교 공고가 데이터에 있음 (공고가 내려가면 건너뜀)', true);
    // ② 제도 질문
    await botAsk(p, '주택청약 2만원씩 넣고 있는데 얼마씩 넣는 게 좋아요?');
    const g = s1.calls.filter(c => c.path === '/free').pop();
    t('② 제도 질문 → /free (공고 없음)', !!g && g.body.listings.length === 0 && g.body.question.includes('2만원'));
    t('② 청약 질문 화면', await p.evaluate(() => !!document.querySelector('.freecard .freeans') && BOT.cur.mode === 'free'));
    t('② 390px 넘침 없음', !(await overflow(p)));
    t('①② 화면 오류 0', !errs.length, errs[0]); await p.close();

    // ③ AI 가 계속 막히면 기본 답
    { const s3 = mk(badLlm); const { p, errs } = await page({ bot_free_answer: true, bot_find_ai: true, bot_find: true }, s3.fn, scheme);
      await botAsk(p, '1순위 조건이 뭐야?');
      const st = await p.evaluate(() => ({ mode: BOT.cur && BOT.cur.mode, fb: BOT.cur && BOT.cur.fallback, txt: document.querySelector('#app').textContent }));
      t('③ 막히면 원문 조각 기본 답(청약 질문 화면)', st.mode === 'general' && st.fb === true && /청약봇 답/.test(st.txt), JSON.stringify({ mode: st.mode, fb: st.fb }));
      t('③ 막힌 답(로또·무조건)이 화면에 없음', !/로또|무조건/.test(st.txt));
      t('③ 화면 오류 0', !errs.length, errs[0]); await p.close(); }

    // ④ 이 공고 물어보기
    { const s4 = mk(goodLlm); const { p, errs } = await page({ bot_free_answer: true, chatbot: true, chat_fab: false, bot_find: false }, s4.fn, scheme);   // 공고 화면 '이 공고 물어보기' 버튼은 둥근 버튼·청약봇 입력 상자가 꺼졌을 때 나온다
      await setProfile(p, PROF);
      const id = has528 ? '2026000528-084.7637A' : await p.evaluate(() => LISTINGS.find(x => !x.sample && !x.rental).id);
      await p.evaluate(id => { S.id = id; go('detail'); }, id);
      const btn = await p.$('[data-chat="open"]'); t('④ 물어보기 버튼', !!btn);
      if (btn) {
        await btn.click(); await p.fill('#chatq', Q); await p.click('.chatform button'); await p.waitForFunction(() => CHAT && !CHAT.busy, null, { timeout: 15000 });
        const c = s4.calls.filter(x => x.path === '/free').pop();
        t('④ /free 로 이 공고 1개 + 내 판정 요약', !!c && c.body.listings.length === 1 && c.body.listings[0].id === id && !!c.body.engine && Array.isArray(c.body.engine.items), c && JSON.stringify({ n: c.body.listings.length, e: !!c.body.engine }));
        const ui = await p.evaluate(() => ({ ans: !!document.querySelector('#chatsheet .chatans .freeans'), up: !!document.querySelector('#chatsheet [data-chat="up"]'), ask: !!document.querySelector('#chatsheet .chatask') }));
        t('④ 자유 답 말풍선·평가·되물음', ui.ans && ui.up && ui.ask, JSON.stringify(ui));
        await p.click('#chatsheet [data-chat="up"]'); await p.waitForTimeout(150);
        t('④ 평가 보냄', s4.calls.some(x => x.path === '/feedback' && x.body.vote === 'up'));
        if (SHOTS) await p.screenshot({ path: `${SHOTS}/free-chat-${scheme}.png` });
        t('④ 390px 넘침 없음', !(await overflow(p)));
      }
      t('④ 화면 오류 0', !errs.length, errs[0]); await p.close(); }

    // ⑥ 스위치 끔 → /free 안 부름
    { const s6 = mk(goodLlm); const { p, errs } = await page({ bot_free_answer: false, bot_find_ai: true, bot_find: true }, s6.fn, scheme);
      await botAsk(p, '1순위 조건이 뭐야?');
      t('⑥ 끄면 /free 를 안 부름(예전 /chat)', !s6.calls.some(c => c.path === '/free') && s6.calls.some(c => c.path === '/chat'), JSON.stringify(s6.calls.map(c => c.path)));
      t('⑥ 화면 오류 0', !errs.length, errs[0]); await p.close(); }
  }
  await b.close();
  const total = Object.values(tally).reduce((n, [a, c]) => n + a + c, 0), bad = Object.values(tally).reduce((n, [, c]) => n + c, 0);
  const out = { date: new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10), checks: total, fails: bad, has528, tally, fail_list: fails };
  writeFileSync(join(ROOT, 'evidence/qa/free-answer.json'), JSON.stringify(out, null, 1));
  console.log(`[청약봇 자유 답변] 검사 ${total} · 실패 ${bad}${fails.length ? '\n' + fails.join('\n') : ''}`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
