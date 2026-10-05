// LH 임대 화면 점검 (기능 lh_rental): 스위치를 켠 설정으로 목록·청년 주택·상세를 390px 밝은·어두운 화면에서 열어 화면 오류, 가로 넘침, 이상한 글자(NaN·undefined)를 본다.
// 스위치를 끈 설정에서는 분양 목록에 '공공임대' 버튼이 없어야 한다(이전과 같음).
// 사용: NODE_PATH=$(npm root -g) node tools/qa/lh_rental.cjs [스크린샷 폴더]  → 문제가 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, existsSync, mkdirSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs'), SHOT = process.argv[2];
const P = { household:'head', selfOwn:false, spouseOwn:false, married:false, birth:'1995-03-01', hhSize:1, hhIncomeYear:3600, income:3600, realEstate:0, carValue:1000,
  cash:2000, liquid:0, deposit:0, townInsurance:0, townFinOther:0, townOtherAsset:0, townDebt:0, youthAsset:3000, kidsMinor:0, everWin:'none', homeSido:'경기', homeSigun:'수원시' };
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
      if (!SHOT || i > 2) continue;
    }
    if (scheme === 'light') console.log('판정 분포: ' + JSON.stringify(judged.reduce((a, [, s]) => (a[s] = (a[s] || 0) + 1, a), {})));
    // 뒤로 가기: 상세 → 임대 목록
    await page.evaluate(() => { S.rcat = 'rent'; S.view = 'rental'; render(); });
    await page.click('[data-ropen]'); await page.waitForTimeout(200); await page.goBack(); await page.waitForTimeout(300);
    if (await page.evaluate(() => S.view) !== 'rental') fails.push(`${scheme}: 뒤로 가기가 임대 목록으로 돌아가지 않음`);
    await page.close();
  }
  await b.close();
  console.log(fails.length ? '[LH 임대 화면] 문제 ' + fails.length + '건\n' + fails.join('\n') : '[LH 임대 화면] 문제 없음');
  process.exit(fails.length ? 1 : 0);
})();
