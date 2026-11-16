// 이용 안내·알림 화면 문구 검사 (2026-11-17 운영자: 애드센스 재심사 직전 점검).
// ① 이용 안내에 '데이터 검증 현황'이 불일치 0건(모두 일치)일 때도 보이고(기능 verify_always), 스위치를 끄면 예전처럼 숨는다
// ② 이용 안내의 가이드 편수가 실제 가이드 수(/guide/ 목록의 링크 수)와 같다 ③ 알림 화면에 '인터뷰에 입력한' 문구가 없다
// 사용: NODE_PATH=$(npm root -g) node tools/qa/about_texts.cjs [스크린샷.png]
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const DOCS = join(__dirname, '../../docs');
const OK_STATUS = { ok: true, at: '2026-11-17 06:00', banner: null, flagged: {}, pending: [], judge: { passed: 974, total: 974 }, golden: { mismatches: [] }, crosscheck: { summary: '[검증·공고문] 시험용' } };
async function run(b, feats, shot) {
  const page = await b.newPage({ viewport: { width: 390, height: 844 } });
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    if (u.pathname === '/verify-status.json') return r.fulfill({ status: 200, body: JSON.stringify(OK_STATUS), contentType: 'application/json' });
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    let body = readFileSync(f);
    if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = Object.assign({}, c.features, feats); body = JSON.stringify(c); }
    r.fulfill({ status: 200, body, contentType: { '.html': 'text/html', '.json': 'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => typeof LISTINGS !== 'undefined' && LISTINGS.length > 0, null, { timeout: 15000 }).catch(() => {});
  await page.evaluate(() => go('about')); await page.waitForTimeout(800);
  const about = await page.evaluate(() => { const t = document.querySelector('#app').innerText; const m = t.match(/해설 (\d+)편/);
    const c = [...document.querySelectorAll('#app section.card')].find(x => x.innerText.includes('데이터 검증 현황'));
    return { card: c ? c.innerText.replace(/\s+/g, ' ').slice(0, 120) : null, guides: m ? Number(m[1]) : null, over: document.documentElement.scrollWidth - document.documentElement.clientWidth }; });
  if (shot) await page.screenshot({ path: shot, fullPage: true });
  await page.evaluate(() => go('alerts')); await page.waitForTimeout(400);
  const alerts = await page.evaluate(() => document.querySelector('#app').innerText);
  await page.close();
  return { about, interview: /인터뷰에 입력한/.test(alerts), src: /인터뷰에 입력한 소득/.test(readFileSync(join(DOCS, 'index.html'), 'utf8')), errs };
}
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const on = await run(b, { verify_always: true, verify_badge: true }, process.argv[2]);
  const off = await run(b, { verify_always: false, verify_badge: true });
  const g = existsSync(join(DOCS, 'guide/index.html')) ? new Set(readFileSync(join(DOCS, 'guide/index.html'), 'utf8').match(/href="\/guide\/[a-z0-9-]+\/"/g) || []).size : null;
  const fails = [];
  if (!on.about.card) fails.push('이용 안내에 데이터 검증 현황이 없음(모두 일치일 때)');
  else if (!/모두 일치/.test(on.about.card)) fails.push('검증 현황 카드에 "모두 일치"가 없음: ' + on.about.card);
  if (off.about.card) fails.push('verify_always 를 껐는데 모두 일치일 때 검증 현황이 보임');
  if (g != null && on.about.guides != null && on.about.guides !== g) fails.push(`이용 안내의 가이드 편수 ${on.about.guides} ≠ 실제 ${g}`);
  if (on.interview || on.src) fails.push("알림 화면에 '인터뷰에 입력한' 문구가 남아 있음");
  if (on.about.over > 0) fails.push(`가로로 ${on.about.over}px 넘침`);
  for (const r of [on, off]) if (r.errs.length) fails.push('화면 오류 ' + r.errs[0]);
  console.log(`[이용 안내 문구 검사] 검증 현황 ${on.about.card ? '보임' : '없음'} · 끄면 ${off.about.card ? '보임' : '숨김'} · 가이드 ${on.about.guides}편(실제 ${g}) · 실패 ${fails.length}` + (fails.length ? '\n  ' + fails.join('\n  ') : ''));
  await b.close();
  process.exit(fails.length ? 1 : 0);
})();
