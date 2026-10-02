// 받은 알림함 검사 (기능: push_inbox). 사용: NODE_PATH=$(npm root -g) node tools/qa/push_inbox.cjs [shot폴더]
// docs 를 localhost 로 열고(서비스 워커가 도는 보안 출처) sw.js 를 등록한 뒤, 크롬 개발자 도구(CDP)로 실제 푸시를 전달한다.
// 확인: ① 알림함(IndexedDB)에 쌓이는지 ② 아래 알림 탭에 안 읽은 수가 뜨는지 ③ 알림 탭에 목록이 보이는지 ④ 열면 읽음·배지 0 ⑤ 누르면 공고로 가는지 ⑥ 스위치를 끄면 목록·표시가 없는지
const { chromium } = require('playwright'); const http = require('node:http'); const { readFileSync, existsSync, mkdirSync } = require('node:fs'); const { join, extname } = require('node:path');
const SHOT = process.argv[2] || '';
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.webmanifest': 'application/manifest+json', '.txt': 'text/plain', '.svg': 'image/svg+xml' };
const flags = { push_inbox: true };
const srv = http.createServer((q, r) => { const u = new URL(q.url, 'http://x'); const f = join('docs', u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
  if (!existsSync(f)) { r.writeHead(404); return r.end(); }
  let body = readFileSync(f);
  if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = { ...c.features, ...flags }; c.push_preview = true; body = JSON.stringify(c); }
  r.writeHead(200, { 'content-type': TYPES[extname(f)] || 'application/octet-stream' }); r.end(body); });
(async () => {
  await new Promise(ok => srv.listen(0, ok)); const base = 'http://localhost:' + srv.address().port;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }), fails = [], errs = [];
  const ok = (c, m) => { if (!c) fails.push(m); console.log(c ? '  ✓' : '  ✗', m); };
  for (const dark of [false, true]) {
    flags.push_inbox = true;
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, colorScheme: dark ? 'dark' : 'light' });
    await ctx.grantPermissions(['notifications'], { origin: base });
    const p = await ctx.newPage(); p.on('pageerror', e => errs.push(e.message));
    await p.goto(base + '/?push=preview', { waitUntil: 'networkidle' });
    await p.evaluate(async () => { await navigator.serviceWorker.register('sw.js', { scope: './' }); await navigator.serviceWorker.ready; });
    const L = await p.evaluate(() => (LISTINGS.find(x => !x.sample) || LISTINGS[0]).id);
    const cdp = await ctx.newCDPSession(p);
    await cdp.send('ServiceWorker.enable');
    const reg = await new Promise(res => { cdp.on('ServiceWorker.workerRegistrationUpdated', e => { const r = e.registrations.find(x => !x.isDeleted); if (r) res(r.registrationId); }); setTimeout(() => res(null), 3000); });
    ok(!!reg, (dark ? '[다크] ' : '[라이트] ') + '서비스 워커 등록');
    const send = d => cdp.send('ServiceWorker.deliverPushMessage', { origin: base + '/', registrationId: reg, data: JSON.stringify(d) });
    await send({ title: '새 공고 · 테스트 단지', body: '경기 · 9월 30일 공고\n10월 14일 특별공급 접수', url: '/#/detail/' + L, tag: 'cp-new' });
    await send({ title: '청약패스 · 내일 마감 1곳', body: '서울 · 테스트 마감 단지', url: '/', tag: 'cp-daily' });
    await p.waitForTimeout(800);
    const stored = await p.evaluate(() => new Promise(ok => { const r = indexedDB.open('cp-inbox', 1); r.onsuccess = () => { const g = r.result.transaction('items').objectStore('items').getAll(); g.onsuccess = () => ok(g.result.length); }; r.onerror = () => ok(-1); }));
    ok(stored === 2, '알림함에 2개 저장 (' + stored + ')');
    await p.waitForTimeout(300);
    const dot = await p.evaluate(() => [...document.querySelectorAll('[data-go="alerts"]')].filter(b => !b.hidden || b.classList.contains('bell')).map(b => b.dataset.unread || '').join(','));
    ok(/2/.test(dot), '알림 탭에 안 읽은 수 2 (' + dot + ')');
    await p.evaluate(() => go('alerts')); await p.waitForTimeout(700);
    const list = await p.evaluate(() => ({ n: document.querySelectorAll('.ibxl li').length, fresh: document.querySelectorAll('.ibx.new').length, first: (document.querySelector('.ibx b') || {}).textContent }));
    ok(list.n === 2 && list.fresh === 2, '알림 탭 목록 2개·새 표시 (' + JSON.stringify(list) + ')');
    if (SHOT) { mkdirSync(SHOT, { recursive: true }); await p.screenshot({ path: join(SHOT, 'inbox-' + (dark ? 'dark' : 'light') + '.png'), fullPage: false }); }
    await p.waitForTimeout(4600);
    const read = await p.evaluate(() => new Promise(ok => { const r = indexedDB.open('cp-inbox', 1); r.onsuccess = () => { const g = r.result.transaction('items').objectStore('items').getAll(); g.onsuccess = () => ok(g.result.filter(x => !x.read).length); }; }));
    ok(read === 0, '열고 나면 모두 읽음 (안 읽음 ' + read + ')');
    const dot2 = await p.evaluate(() => document.querySelectorAll('[data-go="alerts"].unread').length);
    ok(dot2 === 0, '읽은 뒤 안 읽은 표시 없음');
    await p.click('.ibx[href*="detail"]'); await p.waitForTimeout(300);
    const v = await p.evaluate(() => S.view + '/' + S.id);
    ok(v === 'detail/' + L, '누르면 해당 공고로 이동 (' + v + ')');
    await ctx.close();
  }
  // 스위치 끔: 목록·표시 없음
  flags.push_inbox = false;
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 } }); const p = await ctx.newPage(); p.on('pageerror', e => errs.push(e.message));
  await p.goto(base + '/?push=preview', { waitUntil: 'networkidle' }); await p.evaluate(() => go('alerts')); await p.waitForTimeout(400);
  ok(await p.evaluate(() => !document.querySelector('.ibxl') && !/받은 알림/.test(document.getElementById('app').textContent)), '스위치 끄면 받은 알림 없음');
  await ctx.close(); await b.close(); srv.close();
  ok(!errs.length, '화면 오류 없음 ' + errs.slice(0, 3).join(' | '));
  console.log(fails.length ? '[알림함] 실패 ' + fails.length : '[알림함] 모두 통과'); process.exit(fails.length ? 1 : 0);
})();
