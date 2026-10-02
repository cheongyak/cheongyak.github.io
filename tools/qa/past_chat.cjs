// 교차 검사 밖이던 두 화면 검사 (2026-10-02 미뤄둔 일 10번): 지난 공고 '그때 넣었다면' 판정, 청약봇에 보내는 판정 요약.
// A. 지난 공고 (docs/archive/past-judge.json × 대표 조건 3개):
//    A1 화면 줄(pjrow)의 글자가 판정 엔진(eligBucket·spJudge) 결과와 같은지   A2 마감 공고에 '지금 신청 가능'처럼 읽히는 글자(D-day·신청 가능해요·넣어도 돼요)가 없는지
//    A3 주택공급규칙 개정(2026.6.15) 전 공고는 판정 줄이 없는지   A4 판정하지 않는 공고(judgeScope none)가 '신청 가능했어요'로 나오지 않는지   A5 화면 오류
// B. 청약봇 판정 요약 (지금 공고 전부 × 같은 조건 3개):
//    B1 보내는 verdict 가 상세 맨 위 판정(rhero)과 같은 결론인지   B2 마감·판정 범위 밖 공고면 요약(status·reason)에 그 사실이 있는지
//    B3 브라우저가 만드는 요약(chatEnginePayload)과 시험용 Node 요약(chat/tools/engine_payload.cjs — 같은 함수를 부름)이 같은 값인지 (내 조건 정리 방식이 갈라지면 걸림)
// 사용: NODE_PATH=$(npm root -g) node tools/qa/past_chat.cjs → evidence/qa/past-chat.json, 위반이 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
const PROFILES = {   // tools/qa/snapshot.cjs 와 같은 대표 조건
  '서울 신혼 세대주': { household:'head', headSince:'2015-01-01', selfOwn:false, spouseOwn:false, hhHomes:'0', hhNeverOwned:true, win5y:false, recentWin:false, everWin:'none', acctType:'all', acctSince:'2014-01-01', acctAmount:1500, acctCount:120, acctPaid:2000, birth:'1990-03-01', homeSido:'서울', homeSigun:'마포구', sidoOwnSince:'2015-01-01', sidoSince:'2015-01-01', areaSince:'2015-01-01', married:true, marriedOn:'2023-05-01', dependents:2, kidsMinor:1, kidsOnDeed:1, eldersOnDeed:0, youngestBirth:'2025-06-01', pregnant:false, hhSize:3, income:5000, spouseIncome:0, hhIncomeYear:5000, realEstate:0, carValue:1000, cash:3000, taxYears5:true, elder65:false },
  '인천 1인 세대원': { household:'parents', parents60:true, parentsOwn:false, selfOwn:false, hhHomes:'0', win5y:false, everWin:'none', acctType:'all', acctSince:'2020-01-01', acctAmount:300, acctCount:30, acctPaid:500, birth:'1997-01-01', homeSido:'인천', homeSigun:'계양구', sidoOwnSince:'2010-01-01', sidoSince:'2010-01-01', areaSince:'2010-01-01', married:false, dependents:0, kidsMinor:0, kidsOnDeed:0, eldersOnDeed:2, elders1y:2, hhSize:3, income:3500, hhIncomeYear:9000, realEstate:0, carValue:0 },
  '경기 유주택 세대주': { household:'head', headSince:'2012-01-01', selfOwn:true, spouseOwn:false, hhHomes:'1', win5y:false, everWin:'none', acctType:'all', acctSince:'2010-01-01', acctAmount:1000, acctCount:150, acctPaid:1800, birth:'1985-05-01', homeSido:'경기', homeSigun:'성남시', sidoOwnSince:'2012-01-01', sidoSince:'2012-01-01', areaSince:'2012-01-01', married:true, marriedOn:'2014-05-01', dependents:3, kidsMinor:2, kidsOnDeed:2, hhSize:4, income:8000, hhIncomeYear:11000, realEstate:40000, carValue:3000 } };
const HERO_TO_VERDICT = { '신청 가능':'가능', '확인 필요':'확인 필요', '2순위 확인 필요':'확인 필요', '2순위만 가능':'2순위만', '신청 불가':'불가', '특별공급 신청 가능':'가능', '특별공급 확인 필요':'확인 필요' };
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const V = [], N = { pastRows:0, pastCards:0, chat:0 }, errs = [];
  const { loadEngine, buildEngine } = require(join(ROOT, 'chat/tools/engine_payload.cjs'));
  const eng = loadEngine(DOCS);
  for (const [pn, pr] of Object.entries(PROFILES)) {
    const page = await b.newPage({ viewport: { width: 390, height: 900 } }); page.on('pageerror', e => errs.push(pn + ': ' + e.message));
    await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
      const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
      r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
    await page.addInitScript(p => { localStorage.setItem('cy-profile', JSON.stringify(p)); localStorage.setItem('cy-past', '1'); }, pr);
    await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(400);
    // A. 지난 공고
    const A = await page.evaluate(async () => {
      S.profile = syncV2(syncHome(Object.assign({}, DEFAULT_PROFILE, S.profile)));   // 화면에서 저장(save)한 것과 같은 모양으로
      loadPast(); loadPastJudge();
      for (let i = 0; i < 100 && (!PAST || !PJ) && !PAST_ERR && !PJ_ERR; i++) await new Promise(r => setTimeout(r, 100));
      if (!PAST || !PJ) return { err: PAST_ERR || PJ_ERR || '불러오기 실패' };
      const out = [], T = el => el ? el.innerText.replace(/\s+/g, ' ').trim() : '';
      const groups = pastGroups(); S.pjOpen = {}; groups.forEach(g => { S.pjOpen[g.no] = true; });
      S.view = 'past'; S.pn = 100000; S.pq = ''; S.pcat = 'all'; S.psido = ''; render();
      const cards = [...document.querySelectorAll('.pastcard')];
      cards.forEach(c => { const txt = T(c); if (/D-\d|D-day|신청 가능해요|넣어도 돼요|지금 신청/.test(txt)) out.push({ k:'A2 마감 공고에 지금 신청처럼 읽히는 글자', name: T(c.querySelector('b')), text: txt.slice(0, 160) }); });
      let rows = 0;
      for (const gr of groups) {   // 카드마다 판정 칸(pastJudgeHtml)만 따로 그려 본다 — 이름이 같은 공고가 여러 개라 화면 카드와 짝짓지 않는다
        const c = document.createElement('div'); c.innerHTML = pastJudgeHtml(gr);
        const prs = [...c.querySelectorAll('.pjrow')];
        if ((gr.notice || '') < '2026-06-15') { if (prs.length) out.push({ k:'A3 개정 전 공고에 판정 줄', no: gr.no, name: gr.name, notice: gr.notice }); continue; }
        const src = PJ_BY[gr.no]; if (!src) continue;
        if (prs.length !== src.length) { out.push({ k:'A1 판정 줄 수가 주택형 수와 다름', no: gr.no, name: gr.name, rows: prs.length, types: src.length }); continue; }
        src.forEach((x, i) => { rows++;
          const L = fromApi(x), bk = eligBucket(L, S.profile), w = PJ_WORD[bk][1], sp = spTypesFor(L).map(t => spJudge(L, S.profile, t)), spOk = sp.filter(r => r.s === 'ok').length;
          const want = w + (sp.length ? ' · 특공 ' + (spOk ? spOk + '유형 가능' : '가능 없음') : ''), got = T(prs[i].lastElementChild);
          if (got !== want) out.push({ k:'A1 판정 줄 글자 ≠ 엔진', id: x.id, name: x.name, got, want });
          if (on('judge_scope') && judgeScope(L).level === 'none' && bk === 'ok') out.push({ k:'A4 판정하지 않는 공고가 신청 가능했어요', id: x.id, name: x.name, why: judgeScope(L).why });
        });
      }
      return { out, rows, cards: cards.length };
    });
    if (A.err) V.push({ k:'A0 지난 공고 자료를 못 읽음', profile: pn, err: A.err });
    else { A.out.forEach(x => V.push({ profile: pn, ...x })); N.pastRows += A.rows; N.pastCards += A.cards; }
    // B. 청약봇 판정 요약
    const B = await page.evaluate(HERO_TO_VERDICT => {
      const out = [], T = el => el ? el.innerText.replace(/\s+/g, ' ').trim() : '', pays = {};
      for (const L of LISTINGS.filter(x => !x.sample)) {
        S.view = 'detail'; S.id = L.id; render();
        const big = T(document.querySelector('.rhero .rbig')), sub = T(document.querySelector('.rhero .rsub'));
        const hero = big === '접수 마감' ? ((/내 조건으로 보면 (.+?) —/.exec(sub) || [])[1] || '') : big;
        const pay = chatEnginePayload(L, S.profile); pays[L.id] = pay;
        const want = HERO_TO_VERDICT[hero];
        if (!want) out.push({ k:'B1 상세 판정이 청약봇 판정 값으로 옮겨지지 않음', id: L.id, name: L.name, hero, verdict: pay.verdict, reason: pay.reason });
        else if (want !== pay.verdict) out.push({ k:'B1 청약봇 판정 ≠ 상세 판정', id: L.id, name: L.name, hero, verdict: pay.verdict });
        if (statusOf(L) === '마감' && pay.listing.status !== '마감') out.push({ k:'B2 마감 공고인데 요약 상태가 마감 아님', id: L.id, name: L.name, status: pay.listing.status });
        if (on('judge_scope') && judgeScope(L).level === 'none' && !/판정하지 않/.test(pay.reason || '')) out.push({ k:'B2 판정 범위 밖 공고인데 요약에 그 사실이 없음', id: L.id, name: L.name, verdict: pay.verdict, reason: pay.reason });
      }
      return { out, pays };
    }, HERO_TO_VERDICT);
    B.out.forEach(x => V.push({ profile: pn, ...x }));
    // B3. 브라우저 요약 ↔ 시험용 Node 요약 (chat/tools/engine_payload.cjs) — 같은 판정 함수인데 모양이 갈라지면 청약봇 평가가 실제와 달라진다
    for (const [id, pay] of Object.entries(B.pays)) { N.chat++;
      let node; try { node = buildEngine(eng, id, pr); } catch (e) { V.push({ profile: pn, k:'B3 시험용 요약을 못 만듦', id, err: String(e.message || e).slice(0, 120) }); continue; }
      const strip = o => JSON.parse(JSON.stringify(Object.assign({}, o, { data_updated: '' })));
      const a = JSON.stringify(strip(pay)), c = JSON.stringify(strip(node));
      if (a !== c) { const ka = Object.keys(pay), kc = Object.keys(node), diff = [...new Set([...ka, ...kc])].filter(k => k !== 'data_updated' && JSON.stringify(pay[k]) !== JSON.stringify(node[k]));
        V.push({ profile: pn, k:'B3 브라우저 요약 ≠ 시험용 요약', id, fields: diff, browser: diff.map(k => JSON.stringify(pay[k]).slice(0, 120)), node: diff.map(k => JSON.stringify(node[k]).slice(0, 120)) }); }
    }
    await page.close();
  }
  await b.close();
  const by = {}; V.forEach(x => { by[x.k] = (by[x.k] || 0) + 1; });
  writeFileSync(join(ROOT, 'evidence/qa/past-chat.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), profiles: Object.keys(PROFILES).length,
    past_cards: N.pastCards, past_rows: N.pastRows, chat_payloads: N.chat, violations: V.length, kinds: by, examples: V.slice(0, 60), pageErrors: errs.slice(0, 5) }, null, 1) + '\n');
  console.log(`[QA 지난공고·청약봇] 지난 공고 카드 ${N.pastCards} · 판정 줄 ${N.pastRows} · 청약봇 요약 ${N.chat} · 위반 ${V.length}건${errs.length ? ' · 화면 오류 ' + errs.length : ''}`);
  Object.entries(by).sort((a, b) => b[1] - a[1]).forEach(([k, n]) => console.log('  ' + k + ': ' + n));
  V.slice(0, 12).forEach(x => console.log('   ', JSON.stringify(x).slice(0, 260)));
  process.exit(V.length || errs.length ? 1 : 0);
})();
