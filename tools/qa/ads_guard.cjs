// 광고 자리 검사 (2026-11-16 운영자: 애드센스 '게시자 콘텐츠가 없는 화면에 Google 게재 광고' 미승인 — 입력 폼·빈 화면에는 광고 코드·자리가 절대 나오지 않게).
// 광고 스위치(ads)를 켜고 가짜 광고 단위를 넣은 설정으로 화면을 돌며
//   ① 내 조건·알림·가점 컷·이용 안내·만든 이유·약관·방침·등급 기준·온보딩·임대 목록·빈 목록에는 광고 자리(.adbox·ins)가 없고
//   ② 그 화면으로 바로 들어오면(#/me 등) 광고 스크립트도 부르지 않으며
//   ③ 허용 화면(공고가 있는 목록·공고 상세)에만 광고 자리가 나오는지 본다. 광고 서버 요청은 모두 막는다(실제 광고를 부르지 않음).
// 사용: NODE_PATH=$(npm root -g) node tools/qa/ads_guard.cjs
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const DOCS = join(__dirname, '../../docs');
const AD_HOST = /googlesyndication|doubleclick|daumcdn\.net\/kas|google\.com\/adsense/;
async function open(b, hash, adsOn = true) {
  const page = await b.newPage({ viewport: { width: 390, height: 844 } });
  const adReq = [], errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url());
    if (AD_HOST.test(u.href)) { adReq.push(u.hostname); return r.abort(); }
    if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    let body = readFileSync(f);
    if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = Object.assign({}, c.features, { ads: adsOn }); c.adsense_client = 'ca-pub-0000000000000000'; c.adsense_slot_feed = '1111111111'; c.adsense_slot_detail = '2222222222'; c.ads_legal_date = '2026-01-01'; body = JSON.stringify(c); }
    r.fulfill({ status: 200, body, contentType: { '.html': 'text/html', '.json': 'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/' + (hash || ''), { waitUntil: 'networkidle' });
  await page.waitForFunction(() => typeof LISTINGS !== 'undefined' && LISTINGS.length > 0, null, { timeout: 15000 }).catch(() => {});
  return { page, adReq, errs };
}
const slots = page => page.evaluate(() => ({ view: S.view, n: document.querySelectorAll('.adbox, ins.adsbygoogle, ins.kakao_ad_area').length, script: !!document.querySelector('script[src*="adsbygoogle"], script[src*="daumcdn.net/kas"]') }));
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const fails = [], seen = [];
  // ② 광고 없는 화면으로 바로 들어오기 — 광고 자리도, 광고 스크립트도 없어야 한다
  for (const h of ['#/me', '#/alerts', '#/trend', '#/about', '#/story', '#/terms', '#/privacy', '#/grades', '#/rental']) {
    const { page, adReq, errs } = await open(b, h); const r = await slots(page); seen.push(`${h}→${r.view}:${r.n}`);
    if (r.n || r.script || adReq.length) fails.push(`${h}(화면 ${r.view})로 바로 들어왔는데 광고 자리 ${r.n}개 · 스크립트 ${r.script} · 광고 요청 ${adReq.length}`);
    if (errs.length) fails.push(`${h} 화면 오류 ${errs[0]}`);
    await page.close();
  }
  // ①③ 한 화면에서 돌아다니기
  const { page, adReq, errs } = await open(b, '');
  const first = await slots(page);
  const feed = await page.evaluate(() => { S.view = 'feed'; S.q = ''; S.filter = 'all'; render(); return { n: document.querySelectorAll('#app .adbox').length, groups: document.querySelectorAll('#app .card').length }; });
  for (const v of ['me', 'alerts', 'trend', 'about', 'story', 'terms', 'privacy', 'grades', 'onboard', 'rental', 'compare', 'updates']) {
    const r = await page.evaluate(v => { try { go(v); } catch (e) { return { err: e.message }; } return { view: S.view, n: document.querySelectorAll('.adbox, ins.adsbygoogle, ins.kakao_ad_area').length }; }, v);
    seen.push(`${v}:${r.err ? 'x' : r.n}`);
    if (r.n) fails.push(`${v} 화면(${r.view})에 광고 자리 ${r.n}개`);
  }
  const empty = await page.evaluate(() => { S.view = 'feed'; S.q = 'ㅋㅋ없는단지ㅋㅋ'; render(); return { n: document.querySelectorAll('.adbox, ins.adsbygoogle').length, empty: !!document.querySelector('#app .card.empty') }; });
  if (empty.empty && empty.n) fails.push(`조건에 맞는 공고가 없는 빈 목록에 광고 자리 ${empty.n}개`);
  const forced = await page.evaluate(() => { S.view = 'me'; const html = adSlot('feed') + adSlot('detail'); app.insertAdjacentHTML('beforeend', '<aside class="adbox"><ins class="adsbygoogle"></ins></aside>'); render(); return { html, left: document.querySelectorAll('.adbox, ins.adsbygoogle').length }; });
  if (forced.html || forced.left) fails.push(`내 조건 화면에서 adSlot 이 광고를 돌려주거나(${forced.html.length}자) 남은 자리 ${forced.left}개`);
  const detail = await page.evaluate(() => { S.q = ''; const L = LISTINGS.find(x => !x.sample) || LISTINGS[0]; S.id = L.id; go('detail'); return { view: S.view, n: document.querySelectorAll('#app .adbox').length }; });
  if (detail.view !== 'detail' || detail.n !== 1) fails.push(`공고 상세에 광고 자리가 ${detail.n}개 (1개여야 함, 화면 ${detail.view})`);
  if (feed.n > 1) fails.push(`공고 목록에 광고 자리 ${feed.n}개 (최대 1개)`);
  if (errs.length) fails.push('화면 오류 ' + errs[0]);
  await page.close();
  // 스위치 끔: 어디에도 없음
  const off = await open(b, '', false);
  const offR = await off.page.evaluate(() => { S.view = 'feed'; render(); const a = document.querySelectorAll('.adbox, ins.adsbygoogle').length; const L = LISTINGS[0]; S.id = L.id; go('detail'); return a + document.querySelectorAll('.adbox, ins.adsbygoogle').length; });
  if (offR || off.adReq.length) fails.push(`광고 스위치를 껐는데 광고 자리 ${offR}개 · 요청 ${off.adReq.length}`);
  await off.page.close();
  console.log(`[광고 자리 검사] 첫 화면 ${first.view} · 목록 광고 자리 ${feed.n} · 상세 ${detail.n} · 빈 목록 ${empty.n} · 광고 없는 화면 ${seen.join(' ')} · 실패 ${fails.length}` + (fails.length ? '\n  ' + fails.join('\n  ') : ''));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})();
