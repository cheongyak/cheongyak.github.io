// 가점 '입력하기' 흐름 점검 (2026-10-06 사용자 제보: '통장 가입일을 넣으면 계산해요 · 입력하기'를 누르면 내 조건 1단계(사는 곳)가 떠요).
// 빠진 항목(통장 가입일 / 생년월일 / 부양가족 수)마다 그 항목만 비운 조건으로 공고 상세의 가점 칸 '입력하기'를 눌러, 그 칸이 있는 입력 단계가 열리고 커서·표시가 그 칸에 있는지 본다.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/score_input.cjs [docs 폴더] [스크린샷 폴더] → 문제가 있으면 종료 코드 1
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
const DOCS = process.argv[2] || path.join(__dirname, '../../docs'), SHOT = process.argv[3];
const BASE = { homeSido: '서울', homeArea: 'seoul', sidoOwnSince: '2010-01-01', sidoSince: '2010-01-01', areaSince: '2010-01-01', household: 'head', headSince: '2015-01-01', selfOwn: false, married: true, marriedOn: '2018-01-01', spouseOwn: false,
  acctType: 'all', acctSince: '2012-01-01', acctAmount: 1500, hhHomes: '0', hhNeverOwned: true, everWin: 'none', birth: '1988-01-01', dependents: 2, hhSize: 3, kidsMinor: 1, _set: ['spouseOwn', 'acctAmount'] };
const CASES = [['통장 가입일', { acctSince: '' }, 'acctSince'], ['생년월일', { birth: '' }, 'birth'], ['부양가족', { dependents: null }, 'dependents']];
(async () => { const b = await chromium.launch({ executablePath: fs.existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined }); const fails = [];
  for (const [nm, ch, key] of CASES) {
    const p = await b.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true }); const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort(); const f = path.join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!fs.existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: fs.readFileSync(f), contentType: f.endsWith('.json') ? 'application/json' : 'text/html' }); });
    await p.addInitScript(pr => localStorage.setItem('cy-profile', JSON.stringify(pr)), Object.assign({}, BASE, ch));
    await p.goto('http://qa.local/', { waitUntil: 'networkidle' }); await p.waitForTimeout(400);
    const id = await p.evaluate(() => (LISTINGS.find(L => L.houseDtl === '민영' && L.category === 'general' && L.needAccount && myScore(L, S.profile).total == null) || {}).id);
    if (!id) { fails.push(nm + ': 가점 계산 전 공고 없음'); await p.close(); continue; }
    await p.evaluate(id => { S.id = id; S.view = 'detail'; render(); document.querySelectorAll('details').forEach(d => d.open = true); }, id); await p.waitForTimeout(300);
    const btn = p.locator('button', { hasText: '입력하기' }).filter({ has: p.locator('xpath=self::*[@data-edit or @data-action="restart"]') });
    const n = await btn.count(); let target = null;
    for (let i = 0; i < n; i++) { const el = btn.nth(i); if (await el.isVisible() && /넣으면 계산해요/.test(await el.evaluate(e => e.parentElement.textContent))) { target = el; break; } }
    if (!target) { fails.push(nm + ': 가점 칸 입력하기 버튼 없음'); await p.close(); continue; }
    await target.scrollIntoViewIfNeeded(); await target.tap(); await p.waitForTimeout(500);
    const r = await p.evaluate(key => { const h = (document.querySelector('h1') || {}).textContent, a = document.activeElement, box = a && a.closest('.field');
      return { view: S.view, h, focusKey: a && (a.dataset.field || a.dataset.dk || a.dataset.set), marked: box ? box.classList.contains('calcneed') : false }; }, key);
    console.log(nm, JSON.stringify(r));
    if (SHOT) await p.screenshot({ path: path.join(SHOT, 'score-input-' + key + '.png') });
    if (r.view !== 'onboard') fails.push(nm + ': 입력 화면으로 가지 않음 (' + r.view + ')');
    if (r.focusKey !== key) fails.push(nm + ': 커서가 ' + key + ' 칸이 아님 — 화면 "' + r.h + '", 커서 ' + r.focusKey);
    if (errs.length) fails.push(nm + ': 화면 오류 ' + errs.join(' | '));
    await p.close(); }
  await b.close();
  console.log(fails.length ? '문제 ' + fails.length + '건\n' + fails.join('\n') : '가점 입력하기 점검 통과 (' + CASES.length + '가지)'); process.exit(fails.length ? 1 : 0); })();
