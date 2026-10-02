// 저장한 내 조건이 새로고침 뒤에도 그대로인지 (2026-10-02 사용자 제보: 납입 인정 회차 170회가 새로고침하면 0).
// 원인은 깨진 값 정리(cleanProfile, 기능 profile_clean)가 개수 칸을 모두 0~30 으로 묶은 것 — 퍼징은 '나쁜 값이 지워지는지'만 보고 '정상 값이 남는지'는 안 봤다.
// 1) 판정 사례 조건 전부 + 현실적인 큰 값(납입 600회·자산 수십억·1950년생 등)을 기기 저장소에 넣고 새로 열어, 칸마다 값이 같은지
// 2) 실제 입력 화면: 내 조건 편집에서 납입 인정 회차 칸에 170 을 넣고 저장 → 새로고침 → 170 인지
// 사용: NODE_PATH=$(npm root -g) node tools/qa/profile_keep.cjs → evidence/qa/profile-keep.json, 하나라도 바뀌면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
const BIG = { acctCount: 600, acctPaid: 15000, acctAmount: 1570, acctSince: '1990-01-01', birth: '1950-01-01', income: 30000, spouseIncome: 20000, hhIncomeYear: 50000,
  cash: 300000, liquid: 100000, deposit: 50000, realEstate: 500000, carValue: 20000, townDebt: 100000, dependents: 6, kidsMinor: 5, kidsOnDeed: 5, eldersOnDeed: 2, hhSize: 9,
  marriedOn: '1975-05-05', youngestBirth: '2026-09-30', headSince: '1980-01-01', sidoSince: '1950-01-01', loanMonthly: 500 };
(async () => {
  const cases = JSON.parse(readFileSync(join(ROOT, 'tests/judge/cases.json'), 'utf8'));
  const profiles = [...new Map(cases.map(c => [JSON.stringify(c.profile), c.profile])).values()];
  const realistic = [BIG, ...[0, 1, 30, 31, 170, 240, 1200].map(n => ({ acctCount: n, acctSince: '2012-05-05', acctAmount: 1570, acctPaid: 1570 }))];
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage({ viewport: { width: 390, height: 844 } }); const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  const ready = () => page.waitForFunction(() => typeof S !== 'undefined' && typeof LISTINGS !== 'undefined' && LISTINGS.length > 0 && DATA_SOURCE.state !== 'loading', null, { timeout: 15000 }).catch(() => {});
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await ready();
  const fails = []; let n = 0;
  const same = (a, b) => a === b || (a != null && b != null && a !== '' && String(a) === String(b));
  // 1) 실제 불러오기 경로(새로고침)로 — 판정 사례 조건은 묶어서 빠르게(불러오기 함수), 현실적인 큰 값은 하나씩 새로고침
  const viaLoad = await page.evaluate(ps => ps.map(p => { const full = Object.assign({}, DEFAULT_PROFILE, p), c = cleanProfile(full);
    return Object.keys(full).filter(k => JSON.stringify(full[k]) !== JSON.stringify(c[k]) && !(full[k] != null && full[k] !== '' && String(full[k]) === String(c[k]))).map(k => [k, full[k], c[k]]); }), profiles);
  viaLoad.forEach((d, i) => { n++; d.forEach(([k, a, c]) => fails.push(`판정 사례 조건 ${i}: ${k} ${JSON.stringify(a)} → ${JSON.stringify(c)}`)); });
  for (const p of realistic) { n++;
    const saved = await page.evaluate(p => { const full = Object.assign({}, DEFAULT_PROFILE, p); localStorage.setItem('cy-profile', JSON.stringify(full)); return full; }, p);
    await page.reload({ waitUntil: 'domcontentloaded' }); await ready(); await page.waitForTimeout(200);
    const got = await page.evaluate(() => S.profile);
    for (const k of Object.keys(p)) if (!same(saved[k], got[k])) fails.push(`새로고침: ${k} ${JSON.stringify(saved[k])} → ${JSON.stringify(got[k])}`); }
  // 2) 입력 화면으로 넣고 저장 → 새로고침
  { n++; await page.evaluate(() => { localStorage.setItem('cy-profile', JSON.stringify(Object.assign({}, DEFAULT_PROFILE, { acctType: 'all', acctSince: '2012-05-05', acctAmount: 1570, acctPaid: 1570 }))); });
    await page.reload({ waitUntil: 'domcontentloaded' }); await ready();
    const typed = await page.evaluate(() => {   // 내 조건 질문 칸(fieldHtml, 인터뷰·바로 답하기 공용)을 그대로 그려 입력 이벤트로 저장 — 실제 저장 경로
      const fd = { k:'acctCount', type:'count', l:'납입 인정 회차', h:'' }; app.innerHTML = fieldHtml(fd, S.profile);
      const i = document.querySelector('[data-field="acctCount"]'); if (!i) return 'no-input';
      i.value = '170'; i.dispatchEvent(new Event('input', { bubbles: true })); return 'ok'; });
    if (typed === 'no-input') fails.push('입력 화면에서 납입 인정 회차 칸을 못 찾음');
    else { await page.waitForTimeout(300); await page.reload({ waitUntil: 'domcontentloaded' }); await ready(); await page.waitForTimeout(200);
      const v = await page.evaluate(() => S.profile.acctCount); if (v !== 170) fails.push(`입력 화면: 납입 인정 회차 170 넣고 새로고침 → ${JSON.stringify(v)}`); } }
  await b.close();
  writeFileSync(join(ROOT, 'evidence/qa/profile-keep.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), checked: n, fails: fails.length, examples: fails.slice(0, 30), pageErrors: errs.slice(0, 5) }, null, 1) + '\n');
  console.log(`[QA 저장 유지] 내 조건 ${n}개를 저장·새로고침 · 바뀐 칸 ${fails.length}개${errs.length ? ' · 화면 오류 ' + errs.length : ''}`);
  fails.slice(0, 8).forEach(f => console.log('  ', f));
  process.exit(fails.length || errs.length ? 1 : 0);
})();
