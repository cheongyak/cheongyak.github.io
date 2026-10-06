// 공고 상세 '확인이 필요한 조건' 머리의 입력 버튼이 첫 '입력 필요' 항목의 바로 답하기를 열고 그 칸에 커서가 가는지 (2026-10-06 사용자 '청약통장 가입기간 입력하기 누르면 그 칸으로')
// 사용: NODE_PATH=$(npm root -g) node tools/qa/fixlink.cjs → 문제가 있으면 종료 코드 1
const { chromium } = require('playwright'); const { readFileSync, existsSync } = require('fs'); const { join, extname } = require('path');
const DOCS = join(__dirname, '../../docs');
(async () => { const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined }); const page = await b.newPage({ viewport: { width: 390, height: 844 } });
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort(); const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.addInitScript(() => localStorage.setItem('cy-profile', JSON.stringify({ homeSido:'서울', household:'head', selfOwn:false, married:false, hhHomes:'0', cash:50000, birth:'1990-01-01', dependents:1, acctType:'all', acctSince:'', acctAmount:1500 })));
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(800);
  const res = await page.evaluate(() => { const out = [];
    for (const L of LISTINGS.filter(x => !x.sample && x.needAccount).slice(0, 40)) { S.id = L.id; S.fix = null; S.view = 'detail'; render();
      const btn = [...document.querySelectorAll('.ck-h button')][0]; if (!btn) continue;
      out.push({ id: L.id, label: btn.textContent, fix: btn.dataset.fix || null, action: btn.dataset.action || null });
      if (btn.dataset.fix) { btn.click(); const p = document.getElementById('fixpanel'); out[out.length - 1].panel = !!p; out[out.length - 1].fields = p ? [...p.querySelectorAll('[data-field],[data-date],select,input')].map(x => x.dataset.field || x.dataset.date || x.name || x.id).filter(Boolean).slice(0, 4) : []; out[out.length - 1].active = document.activeElement && (document.activeElement.dataset.field || document.activeElement.id); }
      if (out.length >= 4) break; }
    return out; });
  const bad = res.filter(r => !r.fix || !r.panel || !r.active || !String(r.active).includes('acctSince')).map(r => r.id);
  if (!res.length) bad.push('검사할 공고 없음');
  console.log(`[QA 입력 버튼] 공고 ${res.length}개 · 버튼 '${res[0] && res[0].label}' · 문제 ${bad.length + errs.length}`, bad.slice(0, 5), errs.slice(0, 3));
  await b.close(); process.exit(bad.length || errs.length ? 1 : 0); })();
