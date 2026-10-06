// SH 임대 공고 화면 점검 (기능 sh_rental): 스위치를 켠 설정과 끈 설정으로 임대 목록·청년 주택·SH 공고 상세를 390px 에서 연다.
//  켜짐: SH 공고가 목록에 'SH' 표시와 함께 보이고, 청년 대상 SH 공고는 청년 주택에도 보이고, 상세 판정은 '판정 미지원 · 공고문 확인',
//        하단 버튼은 'SH 공고 ↗'(공고 화면 주소) · 모집공고문(공고문 주소), 접수 기간을 못 읽은 공고는 '접수 중'이 아니라 '일정 공고문 확인'.
//  꺼짐: SH 공고가 어디에도 없고 sh-rental.json 을 부르지 않는다(이전과 같음).
// 사용: NODE_PATH=$(npm root -g) node tools/qa/sh_screen.cjs [스크린샷 폴더]  → 문제가 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, existsSync, mkdirSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs'), SHOT = process.argv[2];
const P = { household:'head', selfOwn:false, spouseOwn:false, married:false, birth:'1995-03-01', hhSize:1, hhIncomeYear:3600, income:3600, realEstate:0, carValue:1000,
  cash:2000, liquid:0, deposit:0, townInsurance:0, townFinOther:0, townOtherAsset:0, townDebt:0, youthAsset:3000, kidsMinor:0, everWin:'none', homeSido:'서울', homeSigun:'마포구', hhHomes:'0', pregnant:false,
  _set:['spouseOwn', 'income', 'cash', 'liquid', 'deposit'] };
const BAD = /\bNaN\b|\bundefined\b|\bnull\b|\[object Object\]|출처: 출처/;
const KST = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
const SH_ALL = JSON.parse(readFileSync(join(DOCS, 'sh-rental.json'), 'utf8')).notices;
const shEnd = N => (N.schedule || []).map(x => x.apply_end).filter(Boolean).sort().slice(-1)[0] || N.close || '';
const D30 = new Date(Date.parse(KST) - 30 * 864e5).toISOString().slice(0, 10);
const SH = SH_ALL.filter(N => shEnd(N) ? shEnd(N) >= KST : N.posted >= D30);   // 접수 기간이 지난 공고, 기간을 못 읽었고 30일 넘은 공고는 싣지 않는다
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const fails = [];
  async function open(sh, scheme){
    const page = await b.newPage({ viewport: { width: 390, height: 844 }, colorScheme: scheme });
    const errs = [], asked = []; page.on('pageerror', e => errs.push(e.message));
    await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
      asked.push(u.pathname);
      const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
      let body = readFileSync(f);
      if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = Object.assign({}, c.features, { lh_rental: true, sh_rental: sh }); body = JSON.stringify(c); }
      r.fulfill({ status: 200, body, contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
    await page.addInitScript(p => localStorage.setItem('cy-profile', JSON.stringify(p)), P);
    await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(600);
    return { page, errs, asked };
  }
  const check = async (page, errs, name, full) => {
    const r = await page.evaluate(() => ({ over: document.documentElement.scrollWidth - window.innerWidth, text: document.getElementById('app').innerText }));
    if (r.over > 1) fails.push(`${name}: 가로 넘침 ${r.over}px`);
    const m = BAD.exec(r.text); if (m) fails.push(`${name}: 이상한 글자 '${m[0]}'`);
    if (errs.length) fails.push(`${name}: 화면 오류 ${errs.join(' | ')}`);
    if (SHOT) { mkdirSync(SHOT, { recursive: true }); await page.screenshot({ path: join(SHOT, 'sh-' + name + '.png'), fullPage: !!full }); }
  };
  // 꺼짐
  { const { page, errs, asked } = await open(false, 'light');
    await page.click('[data-rcat="rent"]'); await page.waitForTimeout(800);
    const n = await page.evaluate(() => RENTAL.notices.filter(N => N.org === 'SH').length);
    if (n) fails.push(`꺼짐: SH 공고 ${n}건이 목록에 있음`);
    if (asked.includes('/sh-rental.json')) fails.push('꺼짐: sh-rental.json 을 불러옴');
    if (await page.locator('text=SH 공고').count()) fails.push("꺼짐: 'SH 공고' 문구가 보임");
    await check(page, errs, 'off-rental'); await page.close(); }
  for (const scheme of ['light', 'dark']) {
    const { page, errs } = await open(true, scheme);
    await page.click('[data-rcat="rent"]'); await page.waitForTimeout(800);
    const ids = await page.evaluate(() => RENTAL.notices.filter(N => N.org === 'SH').map(N => N.id));
    if (ids.length !== SH.length) fails.push(`${scheme}: SH 공고 ${ids.length}건 ≠ 마감 전 ${SH.length}건`);
    for (const N of SH_ALL.filter(N => !SH.includes(N))) if (ids.includes(N.id)) fails.push(`${scheme}: 마감된 SH 공고 ${N.id} 가 목록에 있음`);
    const cards = await page.locator('.rcard', { hasText: 'SH' }).count();
    if (!cards) fails.push(`${scheme}: 목록에 SH 카드가 없음`);
    await check(page, errs, `${scheme}-rental`, true);
    // 유형 거르기에 SH 유형이 들어 있는지
    const opts = await page.evaluate(() => [...document.querySelectorAll('[data-rsel="type"] option')].map(o => o.value));
    for (const t of new Set(SH.map(N => N.type))) if (!opts.includes(t)) fails.push(`${scheme}: 유형 거르기에 '${t}' 없음`);
    // 청년 주택
    await page.click('[data-rcat="youth"]'); await page.waitForTimeout(300);
    const yIds = await page.evaluate(() => [...document.querySelectorAll('[data-ropen]')].map(e => e.dataset.ropen));
    for (const N of SH.filter(N => N.youth)) if (!yIds.includes(N.id)) fails.push(`${scheme}: 청년 대상 SH 공고 ${N.id} 가 청년 주택에 없음`);
    await check(page, errs, `${scheme}-youth`);
    // 상세
    for (const N of SH) {
      await page.evaluate(id => { S.rid = id; S.view = 'rdetail'; render(); }, N.id);
      const r = await page.evaluate(() => { const a = document.querySelector('.dcta [data-ev="sh-cta-apply"]'), pdf = document.querySelector('.dcta [data-ev="sh-cta-pdf"]'), hero = document.querySelector('.rhero');
        return { href: a && a.getAttribute('href'), label: a && a.textContent, pdf: pdf && pdf.getAttribute('href'), hero: hero ? hero.innerText : '', dd: (document.querySelector('.rd2-head .dday') || {}).textContent, text: document.getElementById('app').innerText }; });
      const name = `${scheme}-detail-${N.id}`;
      if (r.href !== N.url_mobile) fails.push(`${name}: SH 공고 버튼 주소 ${r.href} ≠ ${N.url_mobile}`);
      if (!/SH 공고/.test(r.label || '')) fails.push(`${name}: 버튼 이름 '${r.label}'`);
      if (N.notice_pdf && r.pdf !== N.notice_pdf) fails.push(`${name}: 모집공고문 버튼 주소 다름`);
      if (!/판정 미지원/.test(r.hero) || !/공고문을 확인/.test(r.hero)) fails.push(`${name}: 판정이 '판정 미지원 + 공고문 확인'이 아님 (${r.hero.slice(0, 60)})`);
      if (/LH 청약플러스/.test(r.text)) fails.push(`${name}: SH 공고 상세에 'LH 청약플러스' 문구`);
      const st = (N.schedule || [])[0];
      if (!st && r.dd !== '일정 공고문 확인') fails.push(`${name}: 접수 기간을 못 읽었는데 배지 '${r.dd}'`);
      if (st && !r.text.includes(st.apply_start.slice(5).replace('-', '.'))) fails.push(`${name}: 접수 시작일 ${st.apply_start} 이 안 보임`);
      if (st && st.rank1 && !r.text.includes('(1순위)')) fails.push(`${name}: 1순위 표시 없음`);
      await check(page, errs, name, scheme === 'light' && N === SH.find(x => x.schedule.length));
    }
    await page.close();
  }
  await b.close();
  console.log(fails.length ? '문제 ' + fails.length + '건\n' + fails.join('\n') : `SH 화면 점검 통과 (마감 전 공고 ${SH.length}/${SH_ALL.length}건 · 켜짐/꺼짐 · 밝은/어두운)`);
  process.exit(fails.length ? 1 : 0);
})();
