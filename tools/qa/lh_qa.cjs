// LH 임대 판정 QA (기능 lh_rental, 2026-10-05 사용자 '저것들도 제대로 된건지 qa 한번 돌려서 오류 확인'):
//  1) 퍼징: 무작위 내 조건 N개 × 지금 임대 공고 전부 → 오류·이상 글자(NaN/undefined/null)·없는 상태 값 0
//  2) 단조성: 소득·총자산·자동차를 늘리면 판정이 좋아지면 안 됨 (ok < check < no, na 는 그대로)
//  3) 답하기 해소: '확인' 항목에 답(q 칸)을 채우면 그 항목이 사라지거나 결론(충족/미충족)으로 바뀌어야 함 — 같은 질문을 계속 묻는 고리 0
//     답할 칸이 없는 '확인'(출산가구 가산·청약예금 등 공고문 확인)은 따로 세어 보고
//  4) 목록 카드 표시 = 상세 판정 (같은 함수)
//  5) 정보 감소 안전성(2026-10-05 외부 QA R3~R5): 내 조건 칸 하나를 지우거나(undefined·null·''·기본값 0/false·입력 표시(_set)만 지움) 공고문 기준 칸 하나를
//     못 읽은 것(null)·완화 아닌 '미적용'·모르는 계층 추가로 바꿔도 계층·공고 결론이 새로 '가능'이 되면 안 된다 (정보가 줄면 확인 또는 그대로)
// 사용: NODE_PATH=$(npm root -g) node tools/qa/lh_qa.cjs [퍼징 수=400]  → 문제가 있으면 종료 코드 1, 요약은 evidence/qa/lh-qa.json
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs'), NF = Number(process.argv[2] || 400);
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage({ viewport: { width: 390, height: 844 } });
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    let body = readFileSync(f);
    if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = Object.assign({}, c.features, { lh_rental: true }); body = JSON.stringify(c); }
    r.fulfill({ status: 200, body, contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
  await page.evaluate(() => new Promise(res => { loadRental(); const t = setInterval(() => { if (RENTAL) { clearInterval(t); res(); } }, 50); }));
  const out = await page.evaluate(NF => {
    const R = { fuzz: 0, fuzzBad: [], mono: 0, monoBad: [], loops: 0, loopBad: [], noQ: {}, card: 0, cardBad: [] };
    let seed = 7; const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
    const pick = a => a[Math.floor(rnd() * a.length)];
    const maybe = (v, pn = 0.15) => rnd() < pn ? null : v;
    const SIDOS = ['서울', '부산', '경남', '전북', '경기', '강원', '대구', '인천'];
    const gen = () => ({ birth: maybe(pick(['1955-01-01', '1961-09-01', '1986-09-15', '1990-06-01', '1995-03-01', '2004-04-01', '2007-09-30', '2008-10-01'])),
      married: maybe(pick([true, false])), marriedOn: pick(['', '2016-01-01', '2020-05-01', '2024-01-01']), spouseOwn: pick([true, false]),
      selfOwn: maybe(pick([true, false, false])), household: pick(['head', 'parents', 'spouse', 'other']), parentsOwn: maybe(pick([true, false])),
      hhSize: maybe(pick([1, 2, 3, 4, 5, 9, 10])), hhIncomeYear: maybe(Math.floor(rnd() * 12000)), income: Math.floor(rnd() * 8000), spouseIncome: pick([0, 0, 3000]),
      realEstate: maybe(Math.floor(rnd() * 50000)), carValue: maybe(pick([0, 1000, 4542, 4543, 6000])), cash: Math.floor(rnd() * 10000), liquid: 0, deposit: pick([0, 5000]),
      townInsurance: maybe(0, 0.3), townFinOther: maybe(0, 0.3), townOtherAsset: maybe(0, 0.3), townDebt: maybe(pick([0, 3000]), 0.3), youthAsset: maybe(Math.floor(rnd() * 30000)),
      kidsMinor: maybe(pick([0, 1, 2])), youngestBirth: pick(['', '2018-01-01', '2022-05-01', '2024-06-01']), pregnant: pick([false, false, true]),
      homeSido: maybe(pick(SIDOS)), homeSigun: pick(['', '창원시', '김해시', '군산시', '남원시', '전주시', '양주시', '마포구']),
      acctType: maybe(pick(['all', 'saving', 'deposit', 'bugeum', 'none', ''])), acctSince: pick(['', '2015-01-01', '2026-06-01']), acctCount: maybe(pick([0, 5, 6, 60])),
      lhStudent: maybe(pick([true, false]), 0.5), lhStudentIncome: maybe(pick([true, false]), 0.5), lhHousingBenefit: maybe(pick([true, false]), 0.5), lhSingleParent: maybe(pick([true, false]), 0.5),
      lhHomeOutside: maybe(pick([true, false]), 0.5), lhStartupRec: maybe(pick([true, false]), 0.5), lhJobCriteria: maybe(pick([true, false]), 0.5), lhLongWorker: maybe(pick([true, false]), 0.5), lhMinorHead: maybe(pick([true, false]), 0.5),
      hhHomes: maybe(pick(['0', '0', '1', '2+']), 0.3), eldersOnDeed: maybe(pick([0, 0, 1]), 0.4), kidsOnDeed: maybe(pick([0, 1]), 0.5), lhPreWed: maybe(pick([true, false]), 0.6), lhBirthKids: maybe(pick([0, 1, 2]), 0.6),
      _set: ZERO_KEYS.filter(() => rnd() < 0.6) });   // 기본값 0·false 칸 중 일부만 '입력함'
    const BAD = /\bNaN\b|\bundefined\b|\[object Object\]|\bnull\b/;
    const ORD = { ok: 0, check: 1, no: 2, na: 3 };
    const NS = RENTAL.notices;
    const judge = (N, p) => rentalJudge(N, Object.assign({}, DEFAULT_PROFILE, p));
    // 답하기에서 넣을 '그럴듯한' 값
    const FILL = { birth: '1993-05-01', married: false, marriedOn: '2022-01-01', youngestBirth: '2021-01-01', selfOwn: false, spouseOwn: false, household: 'head', parentsOwn: false,
      homeSido: '경남', homeSigun: '창원시', hhHomes: '1', eldersOnDeed: 0, acctType: 'all', acctSince: '2015-01-01', acctCount: 60, hhSize: 2, kidsMinor: 1, hhIncomeYear: 3000, youthAsset: 1000,
      realEstate: 0, carValue: 0, cash: 1000, liquid: 0, deposit: 0, townInsurance: 0, townFinOther: 0, townOtherAsset: 0, townDebt: 0, income: 3000, spouseIncome: 0 };
    R.red = 0; R.redBad = []; R.tred = 0; R.tredBad = [];
    const better = (a, b) => b === 'ok' && a !== 'ok';   // 정보를 줄였더니 새로 '가능'
    const cmp = (N, A, B, why, bad) => { if (better(A.s, B.s)) bad.push([N.id, '공고', A.s, B.s, why]);
      A.groups.forEach((g, gi) => { const h = B.groups[gi]; if (h && better(g.s, h.s)) bad.push([N.id, g.key, g.s, h.s, why]); }); };
    for (let i = 0; i < NF; i++) {
      const p = gen();
      for (const N of NS) {
        R.fuzz++;
        let J; try { J = judge(N, p); } catch (e) { R.fuzzBad.push([N.id, 'error ' + e.message]); continue; }
        if (!['ok', 'check', 'no', 'na', 'unknown', 'partial', 'unsupported'].includes(J.s)) R.fuzzBad.push([N.id, 'status ' + J.s]);
        for (const g of J.groups) for (const it of g.items) {
          if (BAD.test(it.t)) R.fuzzBad.push([N.id, g.key, it.t]);
          if (it.s === 'check' && !it.q) R.noQ[it.t.replace(/[\d,]+(원|만원)?/g, '#').slice(0, 60)] = (R.noQ[it.t.replace(/[\d,]+(원|만원)?/g, '#').slice(0, 60)] || 0) + 1;
        }
        // 단조성: 소득·자산·자동차를 늘리면 나빠지거나 그대로
        for (const [k, add] of [['hhIncomeYear', 3000], ['income', 3000], ['realEstate', 20000], ['carValue', 3000], ['youthAsset', 20000]]) {
          if (p[k] == null) continue;
          const q = Object.assign({}, p, { [k]: p[k] + add }); R.mono++;
          const A = judge(N, p), B = judge(N, q);
          A.groups.forEach((g, gi) => { const h = B.groups[gi]; if (g.s !== 'na' && h.s !== 'na' && ORD[h.s] < ORD[g.s]) R.monoBad.push([N.id, g.key, k, g.s, h.s]); });
        }
        // 답하기 해소: q 칸을 채우면 그 확인 항목 문장이 다시 나오지 않아야 함 (최대 4번)
        let cur = Object.assign({}, p);
        for (let round = 0; round < 4; round++) {
          const J2 = judge(N, cur); const asks = [];
          J2.groups.forEach(g => g.items.forEach(it => { if (it.s === 'check' && it.q) asks.push([g.key, it]); }));
          if (!asks.length) break;
          R.loops++;
          const next = Object.assign({}, cur);
          for (const [, it] of asks) for (const k of it.q) next[k] = k.startsWith('lh') ? (k === 'lhBirthKids' ? 1 : true) : FILL[k];   // 사용자가 답하기에서 고친 값
          next._set = [...new Set([...(next._set || []), ...asks.flatMap(([, it]) => it.q)])];
          if (round === 3) { const J3 = judge(N, next); J3.groups.forEach(g => g.items.forEach(it => { if (it.s === 'check' && it.q) R.loopBad.push([N.id, g.key, it.t, it.q.join(',')]); })); }
          cur = next;
        }
      }
    }
    // 5) 정보 감소 안전성 — 내 조건 (퍼징 프로필 앞 NF/4 개 × 공고 × 칸 × 지우는 방식)
    for (let i = 0; i < Math.max(20, NF / 4); i++) {
      const p = Object.assign({}, DEFAULT_PROFILE, gen());
      // 서로 어긋난 입력(세대 0채인데 집 있는 세대원, 1인 세대인데 같은 등본 부모·자녀)은 한쪽을 지우면 나머지가 맞는 정보가 되므로 뺀다
      const pin = p.household === 'parents' || p.eldersOnDeed > 0;
      if ((p.hhHomes === '0' && (p.selfOwn === true || (p.married === true && p.spouseOwn === true) || (pin && p.parentsOwn === true))) ||
          (p.hhSize === 1 && (pin || p.kidsOnDeed > 0 || p.married === true))) { R.contra = (R.contra || 0) + 1; continue; }
      for (const N of NS) {
        const A = rentalJudge(N, p);
        for (const k of Object.keys(DEFAULT_PROFILE)) {
          const ways = [['undefined', undefined], ['null', null], ["''", '']];
          if (ZERO_KEYS.includes(k)) ways.push(['기본값', DEFAULT_PROFILE[k]]);
          for (const [w, v] of ways) { R.red++;
            const q = Object.assign({}, p); if (v === undefined) delete q[k]; else q[k] = v; q._set = (p._set || []).filter(x => x !== k);
            cmp(N, A, rentalJudge(N, q), k + '→' + w, R.redBad); }
          if (ZERO_KEYS.includes(k) && (p._set || []).includes(k)) { R.red++;
            cmp(N, A, rentalJudge(N, Object.assign({}, p, { _set: p._set.filter(x => x !== k) })), k + ' 입력 표시만 지움', R.redBad); }
        }
      }
    }
    // 5-1) 정보 감소 안전성 — 공고문 기준 (읽지 못함·완화 아닌 미적용·모르는 계층)
    const clone = x => JSON.parse(JSON.stringify(x));
    for (let i = 0; i < Math.max(20, NF / 4); i++) {
      const p = Object.assign({}, DEFAULT_PROFILE, gen());
      for (const N of NS) {
        if (!N.terms || !N.terms.groups) continue;
        const A = rentalJudge(N, p);
        const muts = [];
        N.terms.groups.forEach((g, gi) => {
          for (const f of ['income_pct', 'asset_manwon', 'car_manwon', 'homeless', 'age_min', 'age_max', 'dual_add', 'min_family']) if (g[f] != null) muts.push([`${g.key}.${f}=null`, M => { M.terms.groups[gi][f] = null; }]);
          if (N.type !== '공공임대' && !N.terms.relaxed) for (const f of ['income_pct', 'asset_manwon', 'car_manwon']) if (g[f] !== 'excluded') muts.push([`${g.key}.${f}=미적용(완화 아님)`, M => { M.terms.groups[gi][f] = 'excluded'; }]);
          if (g.income_pct && typeof g.income_pct === 'object') muts.push([`${g.key}.income_pct 1인 칸 없음`, M => { M.terms.groups[gi].income_pct = Object.assign({}, g.income_pct, { '1': null, '2': null }); }]);
        });
        if (N.terms.prewed_ok) muts.push(['prewed_ok=없음', M => { delete M.terms.prewed_ok; }]);
        if (N.terms.local) muts.push(['거주 요건 못 읽음', M => { M.terms.local_unread = '현재 ' + N.terms.local.name + '에 거주하는 성년자'; M.terms.local = null; }]);
        if (N.type === '공공임대') { muts.push(['거주지역 못 읽음', M => { M.terms.regions = null; }]); muts.push(['청약통장 요건 못 읽음', M => { M.terms.account = null; }]); }
        if (N.terms.income_table_100) muts.push(['소득 100% 표 없음', M => { M.terms.income_table_100 = null; }]);
        muts.push(['모르는 계층 추가', M => { M.terms.groups.push({ key: '산업단지 근로자', name: '산업단지 근로자', homeless: 'household', income_pct: { '1': 200, '2': 200, '3+': 200 }, asset_manwon: 99999, car_manwon: 9999 }); M.terms.unknown_groups = ['산업단지 근로자']; }]);
        for (const [why, f] of muts) { R.tred++; const M = clone(N); f(M); const B = rentalJudge(M, p);
          // 모르는 계층을 더하면 계층 수가 늘어남 — 기존 계층끼리만 비교하고, 새 계층은 'ok' 이면 안 됨
          cmp(N, A, Object.assign({}, B, { groups: B.groups.slice(0, A.groups.length) }), why, R.tredBad);
          B.groups.slice(A.groups.length).forEach(g => { if (g.s === 'ok') R.tredBad.push([N.id, g.key, '-', g.s, why]); }); }
      }
    }
    // 4) 목록 카드 = 상세 판정
    S.profile = Object.assign({}, DEFAULT_PROFILE, gen(), { birth: '1995-03-01', married: false }); save();
    S.rcat = 'rent'; S.view = 'rental'; render();
    for (const N of NS) { R.card++; const el = document.querySelector(`[data-ropen="${N.id}"] .pill.ok, [data-ropen="${N.id}"] .pill.warn, [data-ropen="${N.id}"] .pill.fail, [data-ropen="${N.id}"] .pill:not(.info):not(.warn)`);
      const J = rentalJudge(N, S.profile), want = R_HEAD[J.s][1], card = document.querySelector(`[data-ropen="${N.id}"]`);
      if (!card || !card.innerText.includes(want)) R.cardBad.push([N.id, want]); }
    return R;
  }, NF);
  out.loopBad = [...new Map(out.loopBad.map(x => [x.join('|'), x])).values()];
  out.fuzzBad = out.fuzzBad.slice(0, 50); out.monoBad = out.monoBad.slice(0, 50); out.redN = out.redBad.length; out.redBad = out.redBad.slice(0, 50); out.tredN = out.tredBad.length; out.tredBad = out.tredBad.slice(0, 50);
  out.pageErrors = errs;
  writeFileSync(join(ROOT, 'evidence/qa/lh-qa.json'), JSON.stringify(out, null, 1) + '\n');
  const bad = out.fuzzBad.length + out.monoBad.length + out.loopBad.length + out.cardBad.length + errs.length + out.redN + out.tredN;
  console.log(`[LH 임대 QA] 퍼징 ${out.fuzz}회 문제 ${out.fuzzBad.length} · 단조성 ${out.mono}회 위반 ${out.monoBad.length} · 답하기 ${out.loops}회 고리 ${out.loopBad.length} · 카드 ${out.card} 다름 ${out.cardBad.length} · 화면 오류 ${errs.length}`);
  console.log(`[LH 임대 QA] 정보 감소 안전성: 내 조건 ${out.red}회 새로 '가능' ${out.redN} · 공고문 기준 ${out.tred}회 새로 '가능' ${out.tredN}`);
  console.log('답할 칸 없는 확인(종류별 횟수): ' + JSON.stringify(Object.entries(out.noQ).sort((a, b) => b[1] - a[1]).slice(0, 15)));
  for (const k of ['fuzzBad', 'monoBad', 'loopBad', 'cardBad', 'redBad', 'tredBad']) if (out[k].length) console.log(k, JSON.stringify(out[k].slice(0, 8)));
  await b.close(); process.exit(bad ? 1 : 0);
})();
