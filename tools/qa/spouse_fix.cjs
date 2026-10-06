// 공고 상세 '배우자 집 답하기'(바로 답하기) 흐름 점검 (2026-10-06 사용자 제보: '배우자 집 공고에서 입력할 때 제대로 입력이 안 되거나 커서가 이상한 곳으로').
// 혼인 중·배우자 명의 집을 아직 답하지 않은 조건으로 공고 상세를 열고 → '배우자 집 답하기'를 누르면
//   ① 바로 답하기 칸 맨 위(빨간 표시·커서)가 '배우자 명의 주택' 질문이고 ② '없어요'가 미리 골라져 있지 않으며 ③ '없어요'를 누르면 무주택 세대가 '충족'으로 바뀌는지 본다.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/spouse_fix.cjs [docs 폴더] [스크린샷 폴더] → 문제가 있으면 종료 코드 1
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path');
const DOCS = process.argv[2] || path.join(__dirname, '../../docs'), SHOT = process.argv[3];
(async () => { const b = await chromium.launch({ executablePath: fs.existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const p = await b.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true }); const errs = [], fails = []; p.on('pageerror', e => errs.push(e.message));
  await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort(); const f = path.join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!fs.existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: fs.readFileSync(f), contentType: f.endsWith('.json') ? 'application/json' : 'text/html' }); });
  await p.addInitScript(() => localStorage.setItem('cy-profile', JSON.stringify({ homeSido: '서울', homeArea: 'seoul', household: 'head', headSince: '2019-01-01', selfOwn: false, married: true, marriedOn: '2022-01-01', acctType: 'all', acctSince: '2016-01-01', acctAmount: 1500, hhHomes: '0', everWin: 'none', hhSize: 2, hhIncomeYear: 8000, income: 5000, _set: ['selfOwn', 'acctAmount', 'income'] })));
  await p.goto('http://qa.local/', { waitUntil: 'networkidle' }); await p.waitForTimeout(400);
  const id = await p.evaluate(() => (LISTINGS.find(L => eligibility(L, S.profile).items.some(i => i.k === '무주택 세대' && /배우자 명의 주택/.test(i.v))) || {}).id);
  if (!id) { console.log('배우자 집 확인 항목이 있는 공고가 없음'); process.exit(1); }
  await p.evaluate(id => { S.id = id; S.view = 'detail'; render(); }, id); await p.waitForTimeout(300);
  const btn = p.locator('[data-fix="무주택 세대"]').first(); await btn.scrollIntoViewIfNeeded(); await btn.tap(); await p.waitForTimeout(600);
  const st = await p.evaluate(() => { const pn = document.getElementById('fixpanel'); const first = pn && pn.querySelector('.fixneed'); const a = document.activeElement;
    return { panel: !!pn, firstQ: first ? (first.querySelector('.lbl,label') || {}).textContent : null, firstKey: first ? (first.querySelector('[data-set],[data-field]') || {}).dataset : null,
      focusIn: a && first ? first.contains(a) : false, focusTxt: a ? (a.textContent || a.getAttribute('aria-label') || a.tagName).slice(0, 40) : null,
      reds: pn ? pn.querySelectorAll('.fixneed').length : 0,
      pre: pn ? [...pn.querySelectorAll('[data-set="spouseOwn"]')].map(x => x.textContent.trim() + ':' + x.getAttribute('aria-checked')) : [] }; });
  console.log('누른 뒤', JSON.stringify(st));
  if (SHOT) await p.screenshot({ path: path.join(SHOT, 'spouse-fix-1.png') });
  if (!st.panel) fails.push('바로 답하기 칸이 열리지 않음');
  if (!st.firstKey || st.firstKey.set !== 'spouseOwn') fails.push('맨 위 질문이 배우자 명의 주택이 아님: ' + st.firstQ);
  if (!st.focusIn) fails.push('커서가 배우자 질문에 있지 않음: ' + st.focusTxt);
  if (st.reds !== 1) fails.push('빨간 표시가 배우자 질문 하나가 아님: ' + st.reds + '개');
  if (st.pre.some(x => x.endsWith(':true'))) fails.push('답하지 않았는데 미리 골라져 있음: ' + st.pre.join(','));
  const no = p.locator('#fixpanel [data-set="spouseOwn"][data-val="false"]').first();
  if (await no.count()) { try { await no.tap({ timeout: 3000 }); } catch (e) { fails.push("'없어요'를 누를 수 없음(접혀 있거나 가려짐)"); } await p.waitForTimeout(500); }
  const after = await p.evaluate(id => { const L = LISTINGS.find(x => x.id === id), it = eligibility(L, S.profile).items.find(i => i.k === '무주택 세대');
    return { s: it.s, v: it.v, set: (S.profile._set || []).includes('spouseOwn'), stat: (document.querySelector('#fixpanel .fixstat') || {}).textContent, checked: [...document.querySelectorAll('#fixpanel [data-set="spouseOwn"]')].map(x => x.textContent.trim() + ':' + x.getAttribute('aria-checked')) }; }, id);
  console.log('없어요 누른 뒤', JSON.stringify(after));
  if (SHOT) await p.screenshot({ path: path.join(SHOT, 'spouse-fix-2.png') });
  if (after.s !== 'ok' || !after.set) fails.push('없어요를 눌렀는데 판정이 안 바뀜: ' + after.s + ' ' + after.v);
  if (errs.length) fails.push('화면 오류 ' + errs.join(' | '));
  console.log(fails.length ? '문제 ' + fails.length + '건\n' + fails.join('\n') : '배우자 집 바로 답하기 점검 통과');
  await b.close(); process.exit(fails.length ? 1 : 0); })();
