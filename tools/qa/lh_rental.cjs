// LH 임대 화면 점검 (기능 lh_rental): 스위치를 켠 설정으로 목록·청년 주택·상세를 390px 밝은·어두운 화면에서 열어 화면 오류, 가로 넘침, 이상한 글자(NaN·undefined)를 본다.
// 스위치를 끈 설정에서는 분양 목록에 '공공임대' 버튼이 없어야 한다(이전과 같음).
// 사용: NODE_PATH=$(npm root -g) node tools/qa/lh_rental.cjs [스크린샷 폴더]  → 문제가 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, existsSync, mkdirSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs'), SHOT = process.argv[2];
const P = { household:'head', selfOwn:false, spouseOwn:false, married:false, birth:'1995-03-01', hhSize:1, hhIncomeYear:3600, income:3600, realEstate:0, carValue:1000,
  cash:2000, liquid:0, deposit:0, townInsurance:0, townFinOther:0, townOtherAsset:0, townDebt:0, youthAsset:3000, kidsMinor:0, everWin:'none', homeSido:'경기', homeSigun:'수원시', hhHomes:'0', pregnant:false,
  _set:['spouseOwn', 'income', 'spouseIncome', 'cash', 'liquid', 'deposit'] };   // 기본값 0·false 칸도 '입력함' (2026-10-05 입력 여부 구분)
const BAD = /\bNaN\b|\bundefined\b|\[object Object\]/;
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const fails = [];
  async function open(lh, scheme){
    const page = await b.newPage({ viewport: { width: 390, height: 844 }, colorScheme: scheme });
    const errs = []; page.on('pageerror', e => errs.push(e.message));
    await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
      const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
      let body = readFileSync(f);
      if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = Object.assign({}, c.features, { lh_rental: lh }); body = JSON.stringify(c); }
      r.fulfill({ status: 200, body, contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
    await page.addInitScript(p => localStorage.setItem('cy-profile', JSON.stringify(p)), P);
    await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(600);
    return { page, errs };
  }
  const check = async (page, errs, name) => {
    const r = await page.evaluate(() => ({ over: document.documentElement.scrollWidth - window.innerWidth, text: document.body.innerText }));
    if (r.over > 1) fails.push(`${name}: 가로 넘침 ${r.over}px`);
    const m = BAD.exec(r.text); if (m) fails.push(`${name}: 이상한 글자 '${m[0]}'`);
    if (errs.length) fails.push(`${name}: 화면 오류 ${errs.join(' | ')}`);
    if (SHOT) { mkdirSync(SHOT, { recursive: true }); await page.screenshot({ path: join(SHOT, name + '.png'), fullPage: /detail-(1|2|5|8)$/.test(name) }); }
  };
  { const { page, errs } = await open(false, 'light');
    if (await page.locator('[data-rcat]').count()) fails.push('스위치 꺼짐: 공공임대 버튼이 보임');
    await check(page, errs, 'off-feed'); await page.close(); }
  for (const scheme of ['light', 'dark']) {
    const { page, errs } = await open(true, scheme);
    if (!(await page.locator('[data-rcat="rent"]').count())) fails.push('스위치 켜짐: 공공임대 버튼이 없음');
    await check(page, errs, `${scheme}-feed`);
    await page.click('[data-rcat="rent"]'); await page.waitForTimeout(800);
    const n = await page.locator('[data-ropen]').count();
    if (!n) fails.push(`${scheme}: 임대 목록 0건`);
    await check(page, errs, `${scheme}-rental`);
    const judged = await page.evaluate(() => RENTAL.notices.map(N => [N.id, rentalJudge(N, S.profile).s]));
    if (judged.some(([, s]) => !['ok', 'check', 'no', 'na', 'unknown'].includes(s))) fails.push('판정 값 이상');
    await page.click('[data-rcat="youth"]'); await page.waitForTimeout(300); await check(page, errs, `${scheme}-youth`);
    const ids = await page.evaluate(() => RENTAL.notices.map(N => N.id));
    for (const [i, id] of ids.entries()) {
      await page.evaluate(id => { S.rid = id; S.view = 'rdetail'; render(); }, id);
      await check(page, errs, `${scheme}-detail-${i}`);
      // 하단 고정 버튼 (기능 lh_cta): LH 청약플러스 공고 주소(API 상세 주소)·모집공고문
      const cta = await page.evaluate(() => { const N = RENTAL.notices.find(x => x.id === S.rid); const a = document.querySelector('.dcta [data-ev="lh-cta-apply"]'), pdf = document.querySelector('.dcta [data-ev="lh-cta-pdf"]');
        return { want: !!(N.url_mobile || N.url), href: a && a.getAttribute('href'), url: N.url_mobile || N.url, pdf: !!pdf, wantPdf: !!N.notice_pdf, pad: document.body.classList.contains('has-cta') }; });
      if (cta.want && cta.href !== cta.url) fails.push(`${scheme}-detail-${i}: 하단 LH 청약플러스 공고 버튼 주소 ${cta.href} ≠ ${cta.url}`);
      if (cta.wantPdf && !cta.pdf) fails.push(`${scheme}-detail-${i}: 하단 모집공고문 버튼 없음`);
      if (!cta.pad) fails.push(`${scheme}-detail-${i}: 하단 버튼 여백(has-cta) 없음`);
      if (!SHOT || i > 2) continue;
    }
    if (scheme === 'light') console.log('판정 분포: ' + JSON.stringify(judged.reduce((a, [, s]) => (a[s] = (a[s] || 0) + 1, a), {})));
    // 목록 요약 (기능 lh_summary): 숫자를 누르면 목록 건수가 그 숫자와 같고, 판정 묶음 합 = 마감 전 공고 수, 다시 누르면 해제
    if (scheme === 'light') {
      const r = await page.evaluate(() => { S.rcat = 'rent'; S.rtype = ''; S.rsido = ''; S.rsum = S.relig = null; S.view = 'rental'; render();
        const out = { bad: [] }, nOf = () => document.querySelectorAll('[data-ropen]').length;
        const all = nOf(); out.all = all;
        [...document.querySelectorAll('[data-rsum]')].map(b => b.dataset.rsum).forEach(k => { const q = () => document.querySelector(`[data-rsum="${k}"]`);   // 누를 때마다 다시 찾는다(다시 그리면 버튼이 바뀜)
          const want = Number(q().querySelector('b').textContent); q().click(); if (nOf() !== want) out.bad.push(`요약 ${k} ${want} ≠ 목록 ${nOf()}`);
          q().click(); if (nOf() !== all) out.bad.push(`요약 ${k} 해제 뒤 ${nOf()} ≠ ${all}`); });
        const open = rentalBase().filter(N => rStatus(N) !== '마감').length; let sum = 0;
        [...document.querySelectorAll('.mc-verdict [data-relig], .mc-verdict span b')].forEach(x => { const b = x.matches('b') ? x : x.querySelector('b'); sum += Number(b.textContent); });
        if (hasProfile() && sum !== open) out.bad.push(`판정 묶음 합 ${sum} ≠ 마감 전 ${open}`);
        [...document.querySelectorAll('[data-relig]')].map(b => [b.dataset.relig, Number(b.querySelector('b').textContent)]).forEach(([k, want]) => {
          document.querySelector(`[data-relig="${k}"]`).click(); const got = nOf();
          const ok = [...document.querySelectorAll('[data-ropen]')].every(c => rBucket(rentalJudge(RENTAL.notices.find(N => N.id === c.dataset.ropen), S.profile).s) === k);
          if (got !== want || !ok) out.bad.push(`판정 ${k} ${want} → 목록 ${got}${ok ? '' : ' (다른 판정 섞임)'}`);
          document.querySelector(`[data-relig="${k}"]`).click(); });
        return out; });
      r.bad.forEach(x => fails.push('요약: ' + x));
      if (SHOT) { await page.evaluate(() => { S.rsum = S.relig = null; render(); window.scrollTo(0, 0); }); await page.screenshot({ path: join(SHOT, 'summary.png') }); }
    }
    // 공고 화면 '답하기' (사용자 10-05 17시): 세대 소득을 비우고 → 확인 항목의 답하기 → 입력·저장 → 판정이 바뀌고 내 조건에 저장되는지
    if (scheme === 'light') {
      const nid = await page.evaluate(() => { S.profile.hhIncomeYear = null; S.profile.household = 'parents'; S.profile.parentsOwn = false; save(); const N = RENTAL.notices.find(N => N.type === '국민임대' && N.terms && N.terms.groups[0].income_pct && N.terms.groups[0].income_pct !== 'excluded'); S.rid = N.id; S.rq = null; S.view = 'rdetail'; render(); return N.id; });
      const before = await page.evaluate(id => rentalJudge(RENTAL.notices.find(N => N.id === id), S.profile).s, nid);
      const btn = page.locator('li', { hasText: '세대 소득 입력 필요' }).locator('[data-rq]').first();
      if (!(await btn.count())) fails.push('답하기 버튼 없음');
      else {
        await btn.click(); await page.waitForTimeout(200);
        if (SHOT) await page.screenshot({ path: join(SHOT, 'answer-open.png'), fullPage: false });
        await page.fill('[data-rqk="hhIncomeYear"]', '3000'); await page.click('[data-action="rq-save"]'); await page.waitForTimeout(200);
        const r = await page.evaluate(id => ({ s: rentalJudge(RENTAL.notices.find(N => N.id === id), S.profile).s, stored: JSON.parse(localStorage.getItem('cy-profile')).hhIncomeYear }), nid);
        if (before !== 'check' || r.s !== 'ok' || r.stored !== 3000) fails.push(`답하기 흐름: 전 ${before} → 후 ${r.s}, 저장 ${r.stored}`);
        await check(page, errs, 'answer-saved');
      }
    }
    // 뒤로 가기: 상세 → 임대 목록
    await page.evaluate(() => { S.rcat = 'rent'; S.view = 'rental'; render(); });
    await page.click('[data-ropen]'); await page.waitForTimeout(200); await page.goBack(); await page.waitForTimeout(300);
    if (await page.evaluate(() => S.view) !== 'rental') fails.push(`${scheme}: 뒤로 가기가 임대 목록으로 돌아가지 않음`);
    await page.close();
  }
  await b.close();
  require('node:fs').writeFileSync(join(ROOT, 'evidence/qa/lh-screen.json'), JSON.stringify({ date: new Date().toISOString(), fails }, null, 1) + '\n');
  console.log(fails.length ? '[LH 임대 화면] 문제 ' + fails.length + '건\n' + fails.join('\n') : '[LH 임대 화면] 문제 없음');
  process.exit(fails.length ? 1 : 0);
})();
