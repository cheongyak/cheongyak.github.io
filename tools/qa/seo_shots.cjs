// 검색용 정적 페이지 화면 검사 (기능 seo_content, 2026-11-04): 390px 밝은·어두운 화면에서 가로 넘침·화면 오류 0, 스크린샷.
// 첫 화면은 ① 자바스크립트 없이(로봇이 보는 글) 미리 그린 블록이 보이는지 ② 앱이 뜨면 그 위를 덮는지 ③ '베타' 표시가 없는지.
// 사용: node tools/qa/seo_shots.cjs [사진 폴더]
const { chromium } = require('playwright'); const { readFileSync, existsSync, mkdirSync } = require('node:fs'); const { join, extname, resolve } = require('node:path');
const ROOT = resolve(__dirname, '..', '..'), DOCS = join(ROOT, 'docs'), OUT = process.argv[2] || '';
const T = { '.html': 'text/html', '.json': 'application/json', '.png': 'image/png', '.js': 'text/javascript', '.mjs': 'text/javascript', '.webmanifest': 'application/manifest+json', '.txt': 'text/plain', '.xml': 'application/xml' };
(async () => {
  if (OUT) mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const fails = []; let n = 0;
  const route = async r => { const u = new URL(r.request().url()); if (u.hostname !== 's.local') return r.abort();
    let f = join(DOCS, decodeURIComponent(u.pathname)); if (u.pathname.endsWith('/')) f = join(f, 'index.html');
    if (!existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: readFileSync(f), contentType: T[extname(f)] || 'application/octet-stream' }); };
  const pick = (dir, re) => { try { return require('node:fs').readdirSync(join(DOCS, dir)).filter(x => re.test(x))[0]; } catch (e) { return null; } };
  const nid = existsSync(join(DOCS, 'notice/2026000528')) ? '2026000528' : pick('notice', /^\d+$/);
  const rid = pick('rental/lh', /^[0-9A-Za-z_-]+$/);
  const paths = ['/notice/', nid && `/notice/${nid}/`, '/notice/type/무순위/', '/notice/경기/', '/rental/', rid && `/rental/lh/${rid}/`, '/guide/', '/guide/score-calc/', '/guide/score/', '/about/operator/', '/about/policy/', '/about/sources/'].filter(Boolean);
  for (const scheme of ['light', 'dark']) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, colorScheme: scheme });
    await ctx.route('**/*', route);
    for (const p of paths) {
      const pg = await ctx.newPage(); const errs = []; pg.on('pageerror', e => errs.push(e.message));
      const res = await pg.goto('http://s.local' + encodeURI(p), { waitUntil: 'load' }); n++;
      if (!res || res.status() !== 200) { fails.push(`${scheme} ${p} 열리지 않음 ${res && res.status()}`); await pg.close(); continue; }
      const ov = await pg.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      const beta = await pg.evaluate(() => /베타/.test((document.querySelector('header') || {}).textContent || '') || /베타/.test((document.querySelector('.betabar') || {}).textContent || ''));
      if (ov) fails.push(`${scheme} ${p} 가로 넘침`); if (errs.length) fails.push(`${scheme} ${p} 오류 ${errs[0]}`); if (beta) fails.push(`${scheme} ${p} 베타 표시 남음`);
      if (OUT) await pg.screenshot({ path: join(OUT, `${scheme}-${p.replace(/[^0-9A-Za-z가-힣]+/g, '_')}.png`) });
      await pg.close();
    }
    // 첫 화면: 자바스크립트 없이 → 미리 그린 블록, 있으면 → 앱이 덮음
    const nojs = await b.newContext({ viewport: { width: 390, height: 844 }, colorScheme: scheme, javaScriptEnabled: false }); await nojs.route('**/*', route);
    const a = await nojs.newPage(); await a.goto('http://s.local/', { waitUntil: 'load' }); n++;
    const pre = await a.evaluate(() => { const x = document.querySelector('#app .seo-pre'); return x ? { len: x.textContent.length, links: x.querySelectorAll('a').length } : null; });
    if (!pre || pre.len < 300 || pre.links < 20) fails.push(`${scheme} 첫 화면(자바스크립트 없이) 미리 그린 글 부족 ${JSON.stringify(pre)}`);
    if (OUT) await a.screenshot({ path: join(OUT, `${scheme}-home-nojs.png`) }); await nojs.close();
    const c = await ctx.newPage(); const errs = []; c.on('pageerror', e => errs.push(e.message));
    await c.goto('http://s.local/', { waitUntil: 'networkidle' }); await c.waitForTimeout(800); n++;
    const st = await c.evaluate(() => ({ pre: !!document.querySelector('#app .seo-pre'), app: (document.getElementById('app').textContent || '').length, beta: /베타/.test((document.querySelector('.brand') || {}).textContent || '') || /베타 ·/.test((document.querySelector('.betabar') || {}).textContent || ''), ov: document.documentElement.scrollWidth > window.innerWidth + 1 }));
    if (st.pre) fails.push(`${scheme} 앱이 뜬 뒤에도 미리 그린 블록이 남음`); if (st.beta) fails.push(`${scheme} 앱 첫 화면 베타 표시 남음`); if (st.ov) fails.push(`${scheme} 앱 첫 화면 가로 넘침`); if (errs.length) fails.push(`${scheme} 앱 오류 ${errs[0]}`);
    if (OUT) await c.screenshot({ path: join(OUT, `${scheme}-home-app.png`) });
    await ctx.close();
  }
  await b.close();
  console.log(`[정적 페이지 화면] ${n}쪽 확인 · 문제 ${fails.length}${fails.length ? '\n' + fails.join('\n') : ''}`);
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
