// 경고 범위 화면 검사 (기능 verify_scope, 2026-10-22): verify-status.json 상태별로 화면이 맞게 보이는지.
//   system  — 모든 판정에 영향(banner) → 모든 화면 위 빨간 경고
//   listing — 특정 공고만(flagged) → 빨간 경고 없음, 그 공고 상세·임대 상세에 '데이터 확인 필요', 이용 안내에 검증 현황 카드
//   pending — 재검증 대기만 → 빨간 경고 없음, 검증 현황 카드에 '재검증 대기'
//   off     — 스위치를 끄면 예전처럼 ok=false 하나로 빨간 경고
// 실행: NODE_PATH=$(npm root -g) node tools/qa/verify_scope.cjs [스크린숏 폴더]   (실패하면 종료 코드 1)
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const DOCS = path.join(__dirname, '..', '..', 'docs'), OUT = process.argv[2] || null;
const base = JSON.parse(fs.readFileSync(path.join(DOCS, 'verify-status.json'), 'utf8'));
const LIST = JSON.parse(fs.readFileSync(path.join(DOCS, 'listings.json'), 'utf8'));
const LID = (Array.isArray(LIST) ? LIST : LIST.listings)[0].id.trim();
const LHID = JSON.parse(fs.readFileSync(path.join(DOCS, 'lh-rental.json'), 'utf8')).notices[0].id;
const FLAG = '자동 검증(데이터 불변식): 시험용 위반';
const RFLAG = '자동 검증(임대 공고문 못 읽음): 시험용 못 읽음';
const S = {
  system: { ...base, ok: false, banner: { kind: 'notice', text: '최근 자동 검증에서 공고문과 다른 값이 발견돼 확인 중이에요.', why: ['공고문 대조 1건'] }, flagged: {}, pending: [] },
  listing: { ...base, ok: false, banner: null, flagged: { [LID]: [FLAG], [LHID]: [RFLAG] }, pending: [] },
  pending: { ...base, ok: true, banner: null, flagged: {}, pending: ['시세 원자료 대조'] },
  off: { ...base, ok: false, banner: null, flagged: { [LID]: [FLAG] }, pending: [] },
};
const want = {
  system: { bad: true, detail: false, rental: false, card: '차이 발견' },
  listing: { bad: false, detail: true, rental: true, card: '공고 2건 확인 중' },
  pending: { bad: false, detail: false, rental: false, card: '재검증 대기' },
  off: { bad: true, detail: false, rental: false, card: null },
};
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const fails = [];
  for (const [name, vs] of Object.entries(S)) {
    const pg = await b.newPage({ viewport: { width: 390, height: 844 } });
    const errs = []; pg.on('pageerror', e => errs.push(e.message));
    await pg.route('**/*', async r => {
      const u = new URL(r.request().url());
      if (u.hostname !== 'qa.local') return r.abort();
      const f = path.join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
      if (!fs.existsSync(f)) return r.fulfill({ status: 404, body: '' });
      let body = fs.readFileSync(f);
      if (u.pathname === '/verify-status.json') body = JSON.stringify(vs);
      if (u.pathname === '/config.json') { const c = JSON.parse(body); if (name === 'off') c.features.verify_scope = false; body = JSON.stringify(c); }
      r.fulfill({ status: 200, body, contentType: f.endsWith('.html') ? 'text/html' : f.endsWith('.mjs') ? 'text/javascript' : 'application/json' });
    });
    await pg.goto('http://qa.local/', { waitUntil: 'networkidle' }); await pg.waitForTimeout(800);
    const bad = await pg.evaluate(() => !!document.querySelector('.betabar.bad'));
    await pg.evaluate(id => { const L = LISTINGS.find(x => x.id.trim() === id); S.id = L.id; go('detail'); }, LID); await pg.waitForTimeout(500);
    const detail = await pg.evaluate(t => document.body.innerText.includes(t), FLAG);
    if (OUT && name === 'listing') await pg.evaluate(() => { const n = document.querySelector('.note.warn'); if (n) n.scrollIntoView(); }).then(() => pg.screenshot({ path: OUT + '/vscope-detail.png' }));
    await pg.evaluate(id => { S.rid = id; go('rdetail'); }, LHID); await pg.waitForTimeout(1500); await pg.evaluate(() => render()); await pg.waitForTimeout(300);
    const rental = await pg.evaluate(t => document.body.innerText.includes(t), RFLAG);
    await pg.evaluate(() => go('about')); await pg.waitForTimeout(500);
    const card = await pg.evaluate(() => { const s = [...document.querySelectorAll('section.card')].find(x => x.innerText.includes('데이터 검증 현황')); return s ? s.innerText : null; });
    if (OUT && name === 'listing') await pg.evaluate(() => { const s = [...document.querySelectorAll('section.card')].find(x => x.innerText.includes('데이터 검증 현황')); if (s) s.scrollIntoView(); }).then(() => pg.screenshot({ path: OUT + '/vscope-card.png' }));
    const w = want[name];
    const got = { bad, detail, rental, card: card ? (card.includes(w.card || '\u0000') ? w.card : card.split('\n').slice(0, 2).join(' ')) : null };
    const ok = got.bad === w.bad && got.detail === w.detail && got.rental === w.rental && (w.card ? got.card === w.card : true) && !errs.length;
    console.log(`[경고 범위·${ok ? '통과' : '실패'}] ${name}: 빨간 경고 ${bad} · 공고 상세 표시 ${detail} · 임대 상세 표시 ${rental} · 검증 현황 ${got.card}${errs.length ? ' · 오류 ' + errs.join('; ') : ''}`);
    if (!ok) fails.push(name);
    await pg.close();
  }
  await b.close();
  console.log(`[경고 범위] ${Object.keys(S).length}가지 상태 중 실패 ${fails.length}`);
  fs.writeFileSync(path.join(__dirname, '..', '..', 'evidence', 'qa', 'verify-scope.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), states: Object.keys(S).length, fails }, null, 1) + '\n');
  process.exit(fails.length ? 1 : 0);
})();
