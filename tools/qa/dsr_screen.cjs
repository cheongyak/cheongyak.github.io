// 대출 계산기 탭(기능 dsr_detail) 화면 점검 — 자금 플랜에는 입력 칸 없이 링크만(2026-11-24), 계산기에서 입력 → 저장 → 다시 계산, 스위치를 끄면 예전 화면, 화면 숫자가 이 파일의 따로 쓴 계산과 같은지.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/dsr_screen.cjs [--shot <png>] → 문제가 있으면 종료 코드 1
const { chromium } = require('playwright'); const { readFileSync, existsSync } = require('fs'); const { join, extname } = require('path');
const DOCS = join(__dirname, '../../docs'); const SHOT = process.argv.includes('--shot') ? process.argv[process.argv.indexOf('--shot') + 1] : null;
const MIME = { '.html':'text/html', '.json':'application/json', '.js':'text/javascript', '.txt':'text/plain', '.css':'text/css', '.svg':'image/svg+xml', '.png':'image/png' };
// 화면 코드와 따로 쓴 계산 (원리금균등)
const pv = (annual, pct, years) => { const r = pct / 100 / 12, n = years * 12; return annual / 12 * (1 - (1 + r) ** -n) / r; };
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const bad = [], errs = [];
  const open = async (features) => { const page = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: SHOT ? 2 : 1 });
    page.on('pageerror', e => errs.push(e.message));
    await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
      const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
      let body = readFileSync(f); if (features && u.pathname === '/config.json') { const c = JSON.parse(body); Object.assign(c.features, features); body = JSON.stringify(c); }
      r.fulfill({ status: 200, contentType: MIME[extname(f)] || 'application/octet-stream', body }); });
    await page.addInitScript(() => { if (!localStorage.getItem('cy-profile')) localStorage.setItem('cy-profile', JSON.stringify({ homeSido:'서울', household:'head', selfOwn:false, married:false, hhHomes:'0', cash:30000, liquid:0, deposit:0, income:8000, loanMonthly:0, birth:'1990-01-01', _set:['cash','liquid','deposit','income'] })); });
    await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(800); return page; };
  const pick = (page, capital) => page.evaluate(cap => { const L = LISTINGS.find(x => !x.sample && !isRental(x) && x.price > 0 && !!(x.capital || x.regulated) === cap); if (!L) return null; S.id = L.id; S.view = 'plan'; planOpt(L).mode = 'live'; render(); return { id: L.id, name: L.name }; }, capital);
  const F = page => page.evaluate(() => { const L = LISTINGS.find(x => x.id === S.id), f = funding(L, S.profile, planOpt(L)); return { loanDsr: f.loanDsr, loan: f.loan, limitBy: f.limitBy, D: f.dsr, gapLive: f.gapLive, available: f.available, total: f.total, html: document.getElementById('app').innerText }; });
  const near = (a, e, what) => { if (!(Math.abs(a - e) < 1e-6)) bad.push(`${what}: 화면 ${a} ≠ 계산 ${e}`); };

  // 1) 켠 화면 — 수도권·규제지역
  let page = await open(null);
  const cap = await pick(page, true);
  if (!cap) bad.push('수도권 공고 없음'); else {
    // 자금 플랜: 입력 카드·월 상환액 줄 없이 링크만 → 누르면 계산기 탭(이 공고 기준)
    if (await page.$('#loancard')) bad.push('자금 플랜에 대출 조건 카드가 남아 있음');
    if (/매달 갚을 돈|내 DSR/.test(await page.innerText('#app'))) bad.push('자금 플랜에 월 상환액·DSR 줄이 남아 있음');
    if (!(await page.$('#tabbar [data-go="loan"]:not([hidden])'))) bad.push('대출 계산 탭 없음');
    await page.click('[data-action="loan-calc"]'); await page.waitForTimeout(150);
    if (await page.evaluate(() => S.view) !== 'loan' || !(await page.$('#loancard')) || !(await page.$('#loanresult'))) bad.push('링크를 눌러도 계산기가 안 열림');
    if (!(await page.innerText('#app')).includes(cap.name)) bad.push('계산기에 공고 이름이 안 보임');
    if (await page.evaluate(() => location.hash) !== '#/loan') bad.push('주소가 #/loan 이 아님');
    let f = await F(page);
    near(f.D.st.add, 3.0, '수도권 변동형 스트레스'); near(f.loanDsr, pv(0.8 * 0.4, 7.0, 30), '기본값 소득 기준 한도(연 8천, 7.0% 30년)');
    // 혼합형 5년 → 3.0 × 80% = 2.4
    await page.click('[data-loanset="type:mix"]'); f = await F(page); near(f.D.st.add, 2.4, '수도권 혼합형 스트레스'); near(f.loanDsr, pv(0.32, 6.4, 30), '혼합형 한도');
    await page.click('[data-loanset="type:cyc"]'); f = await F(page); near(f.D.st.add, 1.2, '수도권 주기형 스트레스');
    await page.click('[data-loanset="type:fix"]'); f = await F(page); near(f.D.st.add, 0, '고정금리 스트레스'); near(f.loanDsr, pv(0.32, 4.0, 30), '고정 한도');
    if (!(await page.$('[data-loanset="years:40"][disabled]'))) bad.push('수도권 40년이 막혀 있지 않음');
    // 금리 3.5% 입력, 신용대출 3000·마통 2000(5%), 그 밖 월 30
    await page.fill('[data-loan="rate"]', '3.5'); await page.dispatchEvent('[data-loan="rate"]', 'change');
    await page.evaluate(() => { document.querySelectorAll('details[data-loanopen]').forEach(d => d.open = true); });
    for (const [k, v] of [['credit', '3000'], ['minus', '2000']]) { await page.evaluate(() => { document.querySelectorAll('details[data-loanopen]').forEach(d => d.open = true); }); await page.fill(`[data-loan="${k}"]`, v); await page.dispatchEvent(`[data-loan="${k}"]`, 'change'); }
    await page.evaluate(() => { document.querySelectorAll('details[data-loanopen]').forEach(d => d.open = true); }); await page.fill('[data-loanp="loanMonthly"]', '30'); await page.dispatchEvent('[data-loanp="loanMonthly"]', 'change');
    f = await F(page);
    const exist = 0.3 / 5 + 0.3 * 0.05 + 0.2 / 5 + 0.2 * 0.05 + 30 * 12 / 10000;
    near(f.D.existing, exist, '지금 대출 연 상환액'); near(f.loanDsr, pv(0.32 - exist, 3.5, 30), '기존 대출 반영 한도(고정 3.5%)');
    // 받을 신용대출 5000 → 연소득 8000 − 5000 = 3000 까지만, 전세대출 1억 → 자금에서 뺌
    for (const [k, v] of [['futCredit', '5000'], ['jeonseLoan', '10000']]) { await page.evaluate(() => { document.querySelectorAll('details[data-loanopen]').forEach(d => d.open = true); }); await page.fill(`[data-loan="${k}"]`, v); await page.dispatchEvent(`[data-loan="${k}"]`, 'change'); }
    f = await F(page);
    near(f.D.fut, 0.3, '받을 신용대출(연소득 한도)'); near(f.D.extra, 0.3 - 1, '추가 조달 − 전세대출'); near(f.gapLive, f.total - f.loan - f.available - (0.3 - 1), '부족분');
    if (!/매달 갚을 돈/.test(f.html) || !/내 DSR/.test(f.html)) bad.push('월 상환액·DSR 줄이 안 보임');
    if (/NaN|undefined|Infinity/.test(f.html)) bad.push('화면에 NaN/undefined');
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('cy-loan')));
    if (!(saved && saved.type === 'fix' && saved.rate === 3.5 && saved.credit === 3000)) bad.push('저장 안 됨 ' + JSON.stringify(saved));
    if (SHOT) await page.screenshot({ path: SHOT, fullPage: true });
    // 자금 플랜으로 돌아가면 같은 숫자가 반영돼 있고, 입력 칸은 없음
    await page.click('[data-action="loan-back"]'); await page.waitForTimeout(150);
    const pl = await page.evaluate(() => ({ view: S.view, card: !!document.getElementById('loancard'), txt: document.getElementById('app').innerText }));
    if (pl.view !== 'plan' || pl.card) bad.push('돌아가기: 자금 플랜이 아니거나 입력 카드가 있음');
    if (!/내 대출 조건 반영/.test(pl.txt) || !/전세대출 갚기/.test(pl.txt)) bad.push('자금 플랜에 대출 조건이 반영됐다는 표시가 없음');
    if (SHOT) await page.screenshot({ path: SHOT.replace(/\.png$/, '-plan.png'), fullPage: true });
    // 공고 없이: 탭으로 들어가 '공고 없이 계산' → 지역·집값
    await page.click('#tabbar [data-go="loan"]'); await page.waitForTimeout(150); await page.click('[data-action="loan-clear"]'); await page.waitForTimeout(150);
    const Q = () => page.evaluate(() => { const q = loanQuick(S.profile); return { loan: q.loan, limitBy: q.limitBy, add: q.dsr.st.add, loanDsr: q.loanDsr, ltv: q.ltvRate, cap: q.cap, txt: document.getElementById('app').innerText }; });
    let q = await Q(); near(q.add, 0, '공고 없이·수도권 고정'); near(q.loan, Math.min(q.loanDsr, 6), '공고 없이 수도권: min(DSR, 6억)');
    await page.click('[data-loanset="zone:loc"]'); await page.click('[data-loanset="type:var"]'); q = await Q(); near(q.add, 0.75, '공고 없이·지방 변동'); near(q.loan, q.loanDsr, '지방·집값 없음 → DSR 한도');
    await page.click('[data-loanset="zone:reg"]'); await page.fill('[data-loan="price"]', '50000'); await page.dispatchEvent('[data-loan="price"]', 'change'); q = await Q();
    near(q.ltv, 0.6, '공고 없이·규제지역 5억: 소득 8천·무주택 세대주 → 서민·실수요자 60%'); near(q.cap, 6, '규제지역 15억 이하 한도');
    if (/NaN|undefined|Infinity/.test(q.txt)) bad.push('계산기(공고 없이)에 NaN/undefined');
    await page.evaluate(id => { S.loanL = null; S.id = id; S.view = 'loan'; render(); }, cap.id);
    // 새로 열어도 유지
    await page.reload({ waitUntil: 'networkidle' }); await page.waitForTimeout(600);
    if (await page.evaluate(() => S.view) !== 'loan') bad.push('#/loan 주소로 새로 열면 계산기가 아님');
    await page.evaluate(id => { S.id = id; S.view = 'plan'; render(); }, cap.id);
    f = await F(page); if (f.D.type !== 'var' || f.D.rate !== 3.5) bad.push('새로 열면 대출 조건이 사라짐');
    // 깨진 저장값
    await page.evaluate(() => { localStorage.setItem('cy-loan', JSON.stringify({ type:'x', rate:'abc', years:999, credit:-5, minus:'많음' })); }); await page.reload({ waitUntil: 'networkidle' }); await page.waitForTimeout(600);
    await page.evaluate(id => { S.id = id; S.view = 'plan'; render(); }, cap.id); f = await F(page);
    if (f.D.type !== 'var' || f.D.rate !== 4 || f.D.years !== 30 || /NaN/.test(f.html)) bad.push('깨진 저장값을 기본값으로 돌리지 못함');
  }
  // 2) 지방: 1.5 × 50% = 0.75, 혼합형 60% → 0.45, 40년 가능
  await page.evaluate(() => localStorage.removeItem('cy-loan')); await page.reload({ waitUntil: 'networkidle' }); await page.waitForTimeout(600);
  const loc = await pick(page, false);
  if (loc) await page.evaluate(() => { S.loanL = S.id; S.view = 'loan'; render(); });
  if (!loc) console.log('[QA 대출 조건] 지방 공고 없음 — 지방 점검 건너뜀'); else {
    let f = await F(page); near(f.D.st.add, 0.75, '지방 변동형 스트레스'); near(f.loanDsr, pv(0.32 - 0.036, 4.75, 30), '지방 기본 한도(그 밖 월 30)');
    await page.click('[data-loanset="type:mix"]'); f = await F(page); near(f.D.st.add, 0.45, '지방 혼합형 스트레스');
    await page.click('[data-loanset="years:40"]'); f = await F(page); if (f.D.years !== 40) bad.push('지방 40년 선택 안 됨');
    await page.click('[data-loanset="years:10"]'); f = await F(page); near(f.D.st.add, 0.75 * 0.2, '지방 혼합형 10년 만기(고정 비중 50%) 스트레스');
  }
  // 2-1) 생애최초 버튼 (기능 first_home_ltv): 지방 70% → '없어요' 80% → '있어요' 70%, 내 정보에 저장
  if (loc) { let r = await page.evaluate(() => { const L = LISTINGS.find(x => x.id === S.id); return funding(L, S.profile, planOpt(L)).ltvRate; }); near(r, 0.7, '지방 일반 LTV');
    await page.click('[data-loanfirst="true"]'); r = await page.evaluate(() => { const L = LISTINGS.find(x => x.id === S.id), f = funding(L, S.profile, planOpt(L)); return [f.ltvRate, f.ltvWhy, JSON.parse(localStorage.getItem('cy-profile')).hhNeverOwned]; });
    if (!(Math.abs(r[0] - 0.8) < 1e-9 && r[1] === '생애최초' && r[2] === true)) bad.push('생애최초 버튼: ' + JSON.stringify(r));
    await page.click('[data-loanfirst="false"]'); r = await page.evaluate(() => { const L = LISTINGS.find(x => x.id === S.id); return funding(L, S.profile, planOpt(L)).ltvRate; }); near(r, 0.7, "'있어요' 뒤 LTV"); }
  await page.close();
  // 3) 스위치를 끄면 예전 화면·예전 계산
  page = await open({ dsr_detail: false, first_home_ltv: false });
  const c2 = await pick(page, true);
  if (c2) { const f = await F(page); if (await page.$('[data-action="loan-calc"]')) bad.push('꺼도 계산기 링크가 보임'); if (await page.$('#tabbar [data-go="loan"]:not([hidden])')) bad.push('꺼도 대출 계산 탭이 보임');
    await page.evaluate(() => { location.hash = '#/loan'; }); await page.waitForTimeout(200); if (await page.evaluate(() => S.view) === 'loan' && await page.$('#loancard')) bad.push('꺼도 #/loan 으로 계산기가 열림'); if (f.D) bad.push('꺼도 dsr 계산'); near(f.loanDsr, pv(0.32, 7.0, 30), '끈 상태 한도(예전 7% 30년)');
    if (/매달 갚을 돈/.test(f.html)) bad.push('꺼도 월 상환액 줄이 보임'); }
  await b.close();
  console.log(`[QA 대출 조건] 수도권 ${cap ? cap.id : '-'} · 지방 ${loc ? loc.id : '-'} · 문제 ${bad.length + errs.length}`, bad.slice(0, 8), errs.slice(0, 3));
  process.exit(bad.length || errs.length ? 1 : 0);
})();
