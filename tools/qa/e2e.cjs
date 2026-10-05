// 사용자 흐름 E2E (2026-10-02 MASTER QA 20·27항): 실제 화면을 눌러 가며 30개 시나리오를 돌린다. 판정 기대값은 화면 판정 함수(eligBucket)와
// 화면 글자의 일치(같은 결론인지)·흐름(뒤로 가기·새로고침·주소로 바로 열기)·화면 오류·이상한 글자(NaN·undefined·null)를 본다. 퍼징: 내 조건에 이상한 값을 넣어도 깨지지 않는지.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/e2e.cjs → evidence/qa/e2e.json, 실패 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
const BASE = { household:'head', headSince:'2015-01-01', selfOwn:false, spouseOwn:false, hhHomes:'0', hhNeverOwned:true, win5y:false, recentWin:false, everWin:'none', acctType:'all',
  acctSince:'2014-01-01', acctAmount:1500, acctCount:120, acctPaid:2000, birth:'1990-03-01', sidoOwnSince:'2015-01-01', sidoSince:'2015-01-01', areaSince:'2015-01-01', married:true,
  marriedOn:'2023-05-01', dependents:2, kidsMinor:1, kidsOnDeed:1, eldersOnDeed:0, youngestBirth:'2025-06-01', pregnant:false, hhSize:3, income:5000, spouseIncome:0, hhIncomeYear:5000,
  realEstate:0, carValue:1000, cash:3000, taxYears5:true, elder65:false };
const BAD = ['', null, -1, 0, 1e12, 'abc', '2026-13-45', '<script>x</script>', 'ㅁ'.repeat(500), '0000-00-00'];
const VIEW_BAD = /\bNaN\b|\bundefined\b|\[object Object\]|\bnull\b(?!\s*값)/;
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const res = [];
  const route = page => page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  const open = async (profile, hash = '') => { const page = await b.newPage({ viewport: { width: 390, height: 844 } }); const errs = []; page.on('pageerror', e => errs.push(e.message));
    await route(page); if (profile) await page.addInitScript(p => localStorage.setItem('cy-profile', JSON.stringify(p)), profile);
    await page.goto('http://qa.local/' + hash, { waitUntil: 'networkidle' }); await page.waitForTimeout(500); return { page, errs }; };
  const heroOf = async page => { const h = page.locator('.rhero'); if (!(await h.count())) return null; const c = await h.getAttribute('class'); return (c.match(/t-(ok|warn|fail|info)/) || [])[1]; };
  const MAP = { ok:'ok', unsure:'warn', r2:'warn', no:'fail' };
  const pickers = { // 시나리오가 고를 공고 (지금 데이터에서 조건으로 찾음 — 날마다 바뀌어도 돌아가게)
    '민영 일반': L => L.category === 'general' && L.houseDtl === '민영' && !genNone(L), '국민 일반': L => L.category === 'general' && L.houseDtl === '국민' && !genNone(L) && !isNewlywedTown(L),
    '신혼희망타운': L => isNewlywedTown(L), '무순위': L => L.supplyType === '무순위', '불법행위 재공급': L => /재공급/.test(L.supplyType || ''), '일반 0세대': L => genNone(L) };
  const profiles = { '서울 신혼': { homeSido:'서울', homeSigun:'마포구' }, '경기 신혼': { homeSido:'경기', homeSigun:'수원시' }, '부산 1인': { homeSido:'부산', homeSigun:'해운대구', married:false, marriedOn:'', dependents:0, kidsMinor:0, kidsOnDeed:0, youngestBirth:'', hhSize:1, income:4000, hhIncomeYear:4000 },
    '유주택': { homeSido:'서울', homeSigun:'강남구', selfOwn:true, hhHomes:'1', hhNeverOwned:false, realEstate:40000 }, '조건 없음': null };
  // 1) 시나리오 6 종류 × 조건 5 = 30: 카드 → 상세 → 자금 플랜 → 뒤로 → 뒤로, 주소로 바로 열기, 새로고침
  const ONLY = process.env.E2E_ONLY;   // E2E_ONLY=lh 이면 LH 임대 시나리오만 (빠른 확인용)
  if (ONLY !== 'lh') for (const [pk, pf] of Object.entries(pickers)) for (const [prn, pr] of Object.entries(profiles)) {
    const name = `${pk} · ${prn}`, fail = [];
    const { page, errs } = await open(pr ? { ...BASE, ...pr } : null);
    const id = await page.evaluate(src => { const f = eval('(' + src + ')'); const L = LISTINGS.find(x => !x.sample && f(x)); return L ? L.id : null; }, pf.toString());
    if (!id) { res.push({ name, status: 'NOT_TESTABLE', why: '지금 데이터에 해당 공고 없음' }); await page.close(); continue; }
    const want = pr ? await page.evaluate(id => ({ ok:'ok', unsure:'warn', r2:'warn', no:'fail' })[eligBucket(LISTINGS.find(x => x.id === id), S.profile)], id) : 'info';
    await page.evaluate(() => { S.showClosed = true; render(); });
    // 주택형 묶음(type_group)이면 카드는 공고의 대표 주택형으로 열린다 → 상세에서 그 주택형 칩(data-topen)을 누른다
    let card = page.locator(`[data-open="${id}"]`).first();
    if (!(await card.count())) card = page.locator(`[data-open^="${id.split('-')[0]}-"]`).first();
    if (!(await card.count())) fail.push('목록에 카드 없음'); else {
      await card.scrollIntoViewIfNeeded(); await card.click(); await page.waitForTimeout(250);
      if (await page.evaluate(() => S.id) !== id) { const t = page.locator(`[data-topen="${id}"]`).first(); if (await t.count()) { await t.click(); await page.waitForTimeout(250); } }
      if (await page.evaluate(() => S.id) !== id) fail.push('그 주택형으로 못 감');
      if (!(await page.evaluate(() => location.hash)).startsWith('#/detail/')) fail.push('상세 주소(#/detail) 아님');
      const h = await heroOf(page); if (h !== want) fail.push(`상세 판정 ${h} ≠ 기대 ${want}`);
      const txt = await page.evaluate(() => document.body.innerText); const m = txt.match(VIEW_BAD); if (m) fail.push('이상한 글자: ' + m[0]);
      const plan = page.locator('[data-go="plan"]').first(); if (await plan.count()) { await plan.click(); await page.waitForTimeout(200);
        if (await page.evaluate(() => S.view) !== 'plan') fail.push('자금 플랜 안 열림');
        await page.goBack(); await page.waitForTimeout(250); if (await page.evaluate(() => S.view) !== 'detail') fail.push('뒤로 가기 → 상세 아님'); }
      await page.reload({ waitUntil: 'networkidle' }); await page.waitForTimeout(500);
      if (await page.evaluate(() => S.view) !== 'detail' || (await heroOf(page)) !== want) fail.push('새로고침 뒤 상세·판정 유지 안 됨');
      await page.goBack(); await page.waitForTimeout(250); if (await page.evaluate(() => S.view) !== 'feed') fail.push('뒤로 가기 → 목록 아님');
    }
    await page.close();
    const dl = await open(pr ? { ...BASE, ...pr } : null, '#/detail/' + encodeURIComponent(id));
    if (await dl.page.evaluate(() => S.view) !== 'detail' || (await heroOf(dl.page)) !== want) fail.push('주소로 바로 열기 실패');
    await dl.page.close();
    if (errs.length || dl.errs.length) fail.push('화면 오류: ' + [...errs, ...dl.errs].slice(0, 2).join(' | '));
    res.push({ name, id, status: fail.length ? 'FAIL' : 'PASS', fail });
  }
  if (ONLY !== 'lh') { // 2) 검색 → 지난 공고 → 그때 넣었다면
  { const name = '검색·지난 공고 흐름', fail = []; const { page, errs } = await open({ ...BASE, homeSido:'서울', homeSigun:'마포구' });
    if (await page.locator('#q').count()) await page.fill('#q', '서울'); else await page.evaluate(() => { S.q = '서울'; render(); }); await page.waitForTimeout(300);
    const bad = await page.evaluate(() => [...document.querySelectorAll('[data-open]')].map(e => LISTINGS.find(L => L.id === e.dataset.open)).filter(L => L && L.sido !== '서울').length); if (bad) fail.push('서울 검색에 다른 지역 ' + bad);
    await page.evaluate(() => { S.q = ''; S.view = 'past'; render(); }); await page.waitForTimeout(800);
    const pj = page.locator('[data-pj]').first(); if (await pj.count()) { await pj.click(); await page.waitForTimeout(800); if (!(await page.locator('.pjrow').count())) fail.push('그때 넣었다면 판정 안 나옴'); } else fail.push('지난 공고 판정 버튼 없음');
    if (errs.length) fail.push('화면 오류: ' + errs[0]); res.push({ name, status: fail.length ? 'FAIL' : 'PASS', fail }); await page.close(); } }
  // 2-1) LH 임대 (기능 lh_rental, 2026-10-05 '일반분양 수준 QA'): 주소로 바로 열기·새로고침·뒤로·없는 공고 번호·이상한 입력
  { const lhOk = async page => page.waitForFunction(() => typeof RENTAL !== 'undefined' && (RENTAL || RENTAL_STATE === 'error'), null, { timeout: 15000 }).catch(() => {});
    const name = 'LH 임대 흐름', fail = []; const { page, errs } = await open({ ...BASE, homeSido:'경남', homeSigun:'창원시', married:false, marriedOn:'', hhSize:1, kidsMinor:0, kidsOnDeed:0, youngestBirth:'', dependents:0 }, '?lh=preview#/rental');
    await page.evaluate(() => loadRental()); await lhOk(page); await page.waitForTimeout(300);
    if (await page.evaluate(() => S.view) !== 'rental') fail.push('#/rental 바로 열기: 화면 ' + await page.evaluate(() => S.view));
    const nCards = await page.locator('[data-ropen]').count(); if (!nCards) fail.push('임대 목록 카드 0');
    const N0 = await page.evaluate(() => { const id = document.querySelector('[data-ropen]').dataset.ropen; return { id, name: RENTAL.notices.find(x => x.id === id).name }; });
    const key = N0.name.slice(0, 12);
    await page.locator(`[data-ropen="${N0.id}"]`).first().click(); await page.waitForTimeout(400);
    const h1 = await page.evaluate(() => location.hash); if (!h1.startsWith('#/rdetail')) fail.push('상세 주소 아님 ' + h1);
    if (!(await page.evaluate(k => !document.querySelector('[data-ropen]') && document.body.innerText.includes(k), key))) fail.push('상세가 아님(목록 카드가 보임) 또는 공고명 없음');
    await page.reload({ waitUntil: 'networkidle' }); await lhOk(page); await page.waitForTimeout(400);
    if (!(await page.evaluate(k => S.view === 'rdetail' && !document.querySelector('[data-ropen]') && document.body.innerText.includes(k), key))) fail.push('상세에서 새로고침하면 그 공고가 아님 (화면 ' + await page.evaluate(() => S.view) + ', 주소 ' + await page.evaluate(() => location.hash) + ')');
    await page.goBack(); await page.waitForTimeout(400); if (await page.evaluate(() => S.view) !== 'rental') fail.push('뒤로 → 임대 목록 아님: ' + await page.evaluate(() => S.view));
    const d2 = await open({ ...BASE }, '?lh=preview#/rdetail/' + encodeURIComponent(N0.id)); await d2.page.evaluate(() => loadRental()); await lhOk(d2.page); await d2.page.waitForTimeout(400);
    if (!(await d2.page.evaluate(k => S.view === 'rdetail' && !document.querySelector('[data-ropen]') && document.body.innerText.includes(k), key))) fail.push('주소로 상세 바로 열기 실패 (화면 ' + await d2.page.evaluate(() => S.view) + ')');
    if (d2.errs.length) fail.push('화면 오류: ' + d2.errs[0]); await d2.page.close();
    const d3 = await open({ ...BASE }, '?lh=preview#/rdetail/zzz-none'); await d3.page.evaluate(() => loadRental()); await lhOk(d3.page); await d3.page.waitForTimeout(300);
    if (await d3.page.evaluate(() => S.view === 'rdetail' && !document.querySelector('[data-ropen]'))) fail.push('없는 공고 번호: 빈 화면');
    if (d3.errs.length) fail.push('없는 공고 번호 화면 오류: ' + d3.errs[0]); await d3.page.close();
    const d4 = await open({ ...BASE }, '#/rental'); await d4.page.waitForTimeout(300);   // 스위치 꺼짐·미리보기 아님 → 일반 목록
    if (await d4.page.evaluate(() => S.view) !== 'feed') fail.push('기능 꺼졌는데 임대 화면 열림'); await d4.page.close();
    if (errs.length) fail.push('화면 오류: ' + errs[0]); res.push({ name, id: N0.id, status: fail.length ? 'FAIL' : 'PASS', fail }); await page.close(); }
  // 2-2) LH 임대 입력 퍼징: 답하기로 저장되는 칸(lh*·homeSigun·eldersOnDeed 등) × 이상한 값 → 임대 목록·상세 오류·이상한 글자 없음
  { const name = 'LH 임대 입력 퍼징', fail = []; let n = 0; const { page, errs } = await open(null, '?lh=preview');
    await page.evaluate(() => loadRental()); await page.waitForFunction(() => RENTAL || RENTAL_STATE === 'error', null, { timeout: 15000 }).catch(() => {});
    const ids = await page.evaluate(() => { const ns = RENTAL.notices, pick = f => (ns.find(f) || {}).id;
      return [pick(N => N.terms && N.terms.local), pick(N => N.terms && N.terms.groups && N.terms.groups.some(g => g.key === '청년')), pick(N => N.terms && N.terms.groups && N.terms.groups.length > 3), pick(N => !N.terms), pick(N => (N.rents || []).length)].filter(Boolean); });
    const LK = ['lhStudent', 'lhStudentIncome', 'lhHousingBenefit', 'lhSingleParent', 'lhHomeOutside', 'lhStartupRec', 'lhJobCriteria', 'lhLongWorker', 'lhBirthKids', 'homeSigun', 'homeSido', 'eldersOnDeed', 'hhHomes', 'kidsMinor', 'hhSize', 'hhIncomeYear', 'carValue', 'birth'];
    for (const k of LK) for (const v of BAD) { n++;
      const r = await page.evaluate(({ k, v, ids, base }) => { try { S.profile = Object.assign({}, DEFAULT_PROFILE, base, { [k]: v }); const out = [];
          S.rcat = 'rent'; S.view = 'rental'; render(); out.push(document.body.innerText);
          ids.forEach(id => { S.rid = id; S.view = 'rdetail'; render(); out.push(document.body.innerText); [...document.querySelectorAll('[data-rq]')].map(b => b.dataset.rq).forEach(q => { S.rq = q; render(); out.push(document.body.innerText); }); S.rq = null; });
          return { ok: true, txt: out.join('\n') }; } catch (e) { return { ok: false, err: e.message }; } }, { k, v, ids, base: { ...BASE, homeSido:'경남', homeSigun:'창원시' } });
      if (!r.ok) fail.push(`${k}=${JSON.stringify(v).slice(0, 20)} → 오류 ${r.err}`); else { const m = r.txt.match(VIEW_BAD); if (m) fail.push(`${k}=${JSON.stringify(v).slice(0, 20)} → '${m[0]}' 표시`); } }
    if (errs.length) fail.push('화면 오류: ' + errs.slice(0, 3).join(' | '));
    res.push({ name: `${name} (${LK.length}칸 × ${BAD.length}값 = ${n}, 공고 ${ids.length})`, status: fail.length ? 'FAIL' : 'PASS', fail: fail.slice(0, 15) }); await page.close(); }
  if (ONLY !== 'lh') {
  // 3) 퍼징: 내 조건 칸마다 이상한 값 10종 → 목록·상세 몇 개를 그려도 오류·이상한 글자 없음
  const keys = Object.keys(BASE).concat(['homeSido', 'homeSigun', 'acctType', 'townType']);
  let fz = 0; const fzFail = [];
  { const { page, errs } = await open(null);   // 깨진 값은 기기 저장소에 넣고 새로 연다 (실제로 생기는 경로)
    const ids = await page.evaluate(() => { const pick = f => (LISTINGS.find(f) || {}).id; return [pick(L => L.houseDtl === '민영'), pick(L => L.houseDtl === '국민'), pick(L => L.supplyType === '무순위'), pick(L => genNone(L)), pick(L => isNewlywedTown(L))].filter(Boolean); });
    for (const k of keys) for (const v of BAD) { fz++;
      await page.evaluate(({ k, v, base }) => localStorage.setItem('cy-profile', JSON.stringify({ ...base, [k]: v })), { k, v, base: { ...BASE, homeSido:'서울', homeSigun:'마포구' } });
      await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForFunction(() => typeof LISTINGS !== 'undefined' && LISTINGS.length > 0 && DATA_SOURCE.state !== 'loading', null, { timeout: 15000 }).catch(() => {});
      const r = await page.evaluate(({ k, v, ids }) => { try { const out = [];
          S.view = 'feed'; render(); out.push(document.body.innerText);
          ids.forEach(id => { S.view = 'detail'; S.id = id; render(); out.push(document.body.innerText); eligBucket(LISTINGS.find(x => x.id === id), S.profile); });
          return { ok: true, txt: out.join('\n') }; } catch (e) { return { ok: false, err: e.message }; } }, { k, v, ids });
      if (!r.ok) fzFail.push(`${k}=${JSON.stringify(v).slice(0, 20)} → 오류 ${r.err}`); else { const m = r.txt.match(VIEW_BAD); if (m) fzFail.push(`${k}=${JSON.stringify(v).slice(0, 20)} → '${m[0]}' 표시`); } }
    if (errs.length) fzFail.push('화면 오류: ' + errs.slice(0, 3).join(' | '));
    await page.close(); }
  res.push({ name: `입력 퍼징 (${keys.length}칸 × ${BAD.length}값 = ${fz})`, status: fzFail.length ? 'FAIL' : 'PASS', fail: fzFail.slice(0, 15) }); }
  await b.close();
  const n = s => res.filter(r => r.status === s).length;
  writeFileSync(join(ROOT, 'evidence/qa/e2e.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), pass: n('PASS'), fail: n('FAIL'), not_testable: n('NOT_TESTABLE'), results: res }, null, 1) + '\n');
  console.log(`[QA E2E] 시나리오 ${res.length}개 · PASS ${n('PASS')} · FAIL ${n('FAIL')} · NOT_TESTABLE ${n('NOT_TESTABLE')}`);
  res.filter(r => r.status === 'FAIL').forEach(r => console.log('  FAIL', r.name, (r.fail || []).slice(0, 4).join(' / ')));
  process.exit(n('FAIL') ? 1 : 0);
})();
