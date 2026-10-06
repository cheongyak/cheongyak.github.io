// 입력 버튼 전수 검사 (2026-10-06 사용자 '다른 입력조건들도 제대로 해당 칸에 접근하는지 전수검사').
// 화면에 있는 '입력하기·답하기·채우기·넣기·고치기' 버튼(data-edit 단계 이동, data-fix 바로 답하기, data-rq 임대 답하기, restart 처음부터, data-go=me)을
// 조건 여러 개 × 공고 상세·목록·내 조건·가점 컷·임대 상세에서 하나씩 실제로 누른다. 누른 뒤:
//   ① 처음부터(restart)인데 내 조건이 이미 있으면 → 문제 '처음부터 다시 시작' (버튼 이름이 '처음부터·전부·다시'면 의도한 것)
//   ② 커서가 간 칸(없으면 빨간 표시 칸, 그것도 없으면 그 단계의 빈칸)이 화면에 보이는지(접힌 칸·숨은 칸이면 문제)
//   ③ 그 칸에 실제 값을 넣어 보면 버튼이 가리키던 판정(그 항목·그 특별공급·가점·임대 계층)이 바뀌는지 — 어떤 값을 넣어도 안 바뀌면 '엉뚱한 칸'
//   ④ 단계 이동인데 그 단계에 빈칸도, 판정을 바꾸는 칸도 없으면 문제
// 사용: NODE_PATH=$(npm root -g) node tools/qa/input_nav.cjs [docs 폴더] [공고 수 제한] → evidence/qa/input-nav.json, 문제가 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = process.argv[2] || join(ROOT, 'docs'), LIM = +process.argv[3] || 0;
const FULL = { homeSido:'경기', homeSigun:'광명시', homeArea:'capital', sidoOwnSince:'2015-01-01', sidoSince:'2015-01-01', areaSince:'2015-01-01', household:'head', headSince:'2016-01-01', selfOwn:false, married:true, marriedOn:'2022-05-01', spouseOwn:false,
  acctType:'all', acctSince:'2014-01-01', acctAmount:1500, acctCount:60, acctPaid:1500, hhHomes:'0', everWin:'none', win5y:false, recentWin:false, birth:'1990-01-01', dependents:2, kidsMinor:1, youngestBirth:'2025-01-01',
  pregnant:false, hhSize:3, kidsOnDeed:1, eldersOnDeed:0, income:5000, spouseIncome:3000, hhIncomeYear:8000, realEstate:0, carValue:1500, hhNeverOwned:true, taxYears5:true, elder65:false, cash:20000, liquid:0, deposit:0 };
const ZK = ['spouseOwn', 'spouseIncome', 'spouseLoan', 'recentWin', 'acctAmount', 'cash', 'liquid', 'deposit', 'income', 'loanMonthly'];
function profiles(){
  let s = 91; const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648;
  const P = [
    ['빠른 시작(미혼)', { homeSido:'서울', homeArea:'seoul', household:'head', headSince:'2019-01-01', selfOwn:false, married:false, acctType:'all', acctSince:'', hhHomes:'0', everWin:'none' }],
    ['빠른 시작(기혼·배우자 미답)', { homeSido:'경기', homeSigun:'광명시', homeArea:'capital', household:'head', headSince:'2019-01-01', selfOwn:false, married:true, marriedOn:'2022-01-01', acctType:'all', acctSince:'2016-01-01', hhHomes:'0', everWin:'none' }],
    ['부모님 세대 청년', { homeSido:'인천', homeSigun:'계양구', household:'parents', selfOwn:false, married:false, acctType:'all', acctSince:'2020-01-01', acctAmount:300, birth:'1999-01-01' }],
    ['다 넣은 신혼', FULL],
  ];
  for (let i = 0; i < 3; i++) { const q = {}; Object.keys(FULL).forEach(k => { if (rnd() < 0.55) q[k] = FULL[k]; }); q.homeSido = ['서울', '경기', '인천'][i]; P.push(['무작위 ' + (i + 1), q]); }
  return P.map(([n, p]) => [n, Object.assign({}, p, { _set: Object.keys(p).filter(k => ZK.includes(k)) })]);
}
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage({ viewport: { width: 390, height: 844 } }); const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(500);
  await page.evaluate(() => { try { if (typeof lhOn === 'function' && lhOn()) loadRental(); } catch(e) {} }); await page.waitForTimeout(800);
  const out = await page.evaluate(async ([PROFS, LIM]) => {
    const tick = () => new Promise(r => requestAnimationFrame(() => setTimeout(r, 20)));
    const INPUT = /입력|답하기|채우|넣기|고치기|답하면/;
    const OKRESTART = /처음부터|전부|다시|내 조건 입력하기|입력하기$/;   // 내 조건이 없을 때의 '입력하기'는 처음부터가 맞다 — 내 조건이 있으면 아래에서 따로 본다
    const btns = () => [...app.querySelectorAll('button,a')].filter(e => e.dataset.edit || e.dataset.fix || e.dataset.rq || ['restart', 'sp-input', 'sp-home'].includes(e.dataset.action) || (e.dataset.go === 'me' && INPUT.test(e.textContent)));
    const desc = e => (e.dataset.edit ? 'edit:' + e.dataset.edit + (e.dataset.focus ? '>' + e.dataset.focus : '') : e.dataset.fix ? 'fix:' + e.dataset.fix : e.dataset.rq ? 'rq:' + e.dataset.rq : e.dataset.action ? 'action:' + e.dataset.action : 'go:me') + ' "' + e.textContent.trim().slice(0, 30) + '"';
    const ctxOf = e => { const c = e.closest('.ckwarn,.ckitem,li,.sp-row,.sprow,.card,.note,section'); return c ? c.innerText.replace(/\s+/g, ' ').slice(0, 90) : ''; };
    const keyOf = el => el && (el.dataset.field || el.dataset.dk || el.dataset.set || el.dataset.rqk);
    const visible = el => { if (!el || !el.isConnected) return false; if (el.closest('details:not([open])') && !el.closest('summary')) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    // 칸 하나에 넣어 볼 값들
    const fdOf = k => (typeof fieldVariants === 'function' ? fieldVariants(k) : []).find(f => !f.show || f.show(S.profile)) || (fieldVariants(k) || [])[0];
    const LQ = typeof LH_Q !== 'undefined' ? LH_Q : {};
    const cands = k => { const fd = fdOf(k);
      if (fd && fd.type === 'choice') return fd.o.map(o => o[0]);
      const t = fd ? fd.type : LQ[k] ? LQ[k][1] : null;
      if (t === 'yn') return [true, false];
      if (t === 'date') return ['1955-01-01', '1987-06-01', '1996-01-01', '2008-01-01', '2016-01-01', '2019-12-01', '2023-06-01', '2025-03-01', '2026-08-01'];
      if (t === 'count') return [0, 1, 2, 3, 6, 24, 60, 200];
      if (t === 'text') return ['광명시', '성남시', '계양구', '수원시'];
      if (t === 'sido') return ['서울', '경기', '인천', '부산'];
      if (fd && fd.type === 'money' || t === 'money' || t == null) return [0, 300, 3000, 9000, 30000, 300000];
      if (LQ[k] && LQ[k][1] === 'choice') return LQ[k][2].map(o => o[0]);
      return [0, 1, 3]; };
    const withV = (p, k, v) => { const q = JSON.parse(JSON.stringify(p)); q[k] = v; markSet(q, k, true); try { syncHome(q); } catch(e) {} return q; };
    // 버튼이 가리키는 판정
    const sigFn = (kind, arg, L, N) => {
      if (kind === 'fix' && /^sp:/.test(arg)) { const ts = arg === 'sp:all' ? spTypesFor(L) : [arg.slice(3)]; return p => ts.map(t => { const r = spJudge(L, p, t); return r.s + (r.warn || []).join('|') + (r.stage ? r.stage[0] : ''); }).join(';'); }
      if (kind === 'fix' && typeof PEND_FIX !== 'undefined' && PEND_FIX[arg]) return p => String(pendingChecks(L, p).includes(arg)) + spTypesFor(L).map(t => spJudge(L, p, t).s).join('');
      if (kind === 'fix') return p => { const it = eligibility(L, p).items.find(i => i.k === arg); return it ? it.s + it.v : 'none'; };
      if (kind === 'rq') { const [gk, ix] = arg.split('|'); return p => { const J = rentalJudge(N, p), g = J.groups.find(x => x.key === gk); return g ? g.s + JSON.stringify(g.items.map(i => i.s + i.t)) : 'none'; }; }
      if (kind === 'score') return p => { const s = myScore(L, p); return s.total + '|' + s.miss.join(','); };
      if (L) return p => { const e = eligibility(L, p); return e.items.map(i => i.k + i.s + i.v).join(';') + '#' + spTypesFor(L).map(t => spJudge(L, p, t).s).join('') + '#' + (myScore(L, p).total) + '#' + eligBucket(L, p); };
      if (N) return p => JSON.stringify(rentalJudge(N, p).groups.map(g => g.s + g.items.map(i => i.s + i.t).join()));
      return p => LISTINGS.filter(x => statusOf(x) !== '마감').map(x => eligBucket(x, p)).join('');
    };
    /* 칸 k 가 판정을 바꾸는지. 항목에 따라 두 칸을 함께 답해야 판정되는 경우(집 소유 + 세대 구성 등)가 있어, 같이 표시된 다른 빈칸(others)에 첫 값을 넣은 상태에서도 본다 */
    const relevant = (sig, p0, k, others) => { const bases = [p0];
      if (others && others.length) { let q = p0; others.filter(o => o !== k).forEach(o => { const c = cands(o); if (c.length) q = withV(q, o, c[0]); }); bases.push(q);
        others.filter(o => o !== k).forEach(o => cands(o).slice(1, 3).forEach(v => bases.push(withV(q, o, v)))); }
      for (const b0 of bases) { const base = sig(b0); for (const v of cands(k)) { try { if (sig(withV(b0, k, v)) !== base) return true; } catch(e) {} } } return false; };
    const res = { clicks: 0, byKind: {}, problems: {}, notes: {} };
    const prob = (kind, key, ex) => { const o = (kind === 'note' ? res.notes : res.problems); (o[key] = o[key] || { n: 0, ex: [] }).n++; if (o[key].ex.length < 3) o[key].ex.push(ex); };
    const byNo = {}; LISTINGS.filter(L => !L.sample).forEach(L => { const k = L.id.split('-')[0]; (byNo[k] = byNo[k] || []).push(L); });
    let Ls = Object.values(byNo).map(a => a[0]); if (LIM) Ls = Ls.slice(0, LIM);
    const RN = (typeof RENTAL !== 'undefined' && RENTAL && RENTAL.notices) ? RENTAL.notices.filter(N => N.terms) : [];
    const scenes = [];
    Ls.forEach(L => scenes.push(['상세 ' + L.id, () => { S.id = L.id; S.view = 'detail'; S.fix = null; S.rq = null; render(); app.querySelectorAll('details').forEach(d => d.open = true); }, L, null]));
    scenes.push(['목록', () => { S.view = 'feed'; S.fix = null; render(); }, null, null]);
    scenes.push(['내 조건', () => { S.view = 'me'; render(); }, null, null]);
    if (typeof VIEWS !== 'undefined' && VIEWS.trend) Ls.slice(0, 20).forEach(L => scenes.push(['가점 컷 ' + L.id, () => { S.id = L.id; S.view = 'trend'; render(); }, L, null]));
    RN.forEach(N => scenes.push(['임대 ' + N.id, () => { S.rid = N.id; S.view = 'rdetail'; S.rq = null; render(); app.querySelectorAll('details').forEach(d => d.open = true); }, null, N]));
    for (const [pn, pr] of PROFS) {
      const P0 = Object.assign({}, DEFAULT_PROFILE, pr); try { syncHome(P0); syncV2(P0); } catch(e) {}
      for (const [sn, setup, L, N] of scenes) {
        S.profile = JSON.parse(JSON.stringify(P0)); save(); S.quick = false; setup(); await tick();
        const list = btns().map(desc); const seen = new Set();
        for (let i = 0; i < list.length; i++) {
          if (seen.has(list[i])) continue; seen.add(list[i]);
          S.profile = JSON.parse(JSON.stringify(P0)); save(); S.quick = false; S.fix = null; S.rq = null; setup(); await tick();
          const hadProfile = hasProfile();
          const el = btns()[i]; if (!el) continue; const d = desc(el), ctx = ctxOf(el), label = el.textContent.trim();
          const kind = el.dataset.fix ? 'fix' : el.dataset.rq ? 'rq' : el.dataset.edit && el.dataset.focus ? 'score' : el.dataset.edit ? 'edit' : el.dataset.action || 'go';
          const sig = sigFn(kind, el.dataset.fix || el.dataset.rq, L, N);
          const ex = { profile: pn, scene: sn, button: d, ctx };
          try { if (el.dataset.fix && L && !/^sp:/.test(el.dataset.fix)) { const it = eligibility(L, S.profile).items.find(i => i.k === el.dataset.fix); if (it) ex.item = it.s + ' · ' + it.v + ' · ' + (it.note || '').slice(0, 80); } } catch(e) {}
          ex.p = Object.fromEntries(Object.entries(pr).filter(([k]) => k !== '_set'));
          res.clicks++; res.byKind[kind] = (res.byKind[kind] || 0) + 1;
          const wasView = S.view; el.click(); await tick(); await tick();
          const act = document.activeElement, fk = keyOf(act), reds = [...app.querySelectorAll('.fixneed')].map(x => keyOf(x.querySelector('[data-field],[data-dk],[data-set],[data-rqk]'))).filter(Boolean);
          ex.landed = S.view === 'onboard' ? 'onboard:' + stepKey(visibleSteps()[S.step] || {}) : S.view; ex.focus = fk || null; ex.reds = reds.slice(0, 4);
          if (kind === 'restart' || kind === 'sp-input' || kind === 'sp-home') {
            if (hadProfile && !/처음부터|전부|다시/.test(label)) prob('problem', '내 조건이 있는데 처음부터 다시 시작 (' + label + ')', ex);
            continue; }
          if (kind === 'go') { prob('note', '내 조건 화면으로만 이동 (' + label + ')', ex); continue; }
          // 도착 칸
          const target = fk || reds[0] || null, panelKeys = [...app.querySelectorAll('#fixpanel [data-field],#fixpanel [data-dk],#fixpanel [data-set],#rqpanel [data-rqk]')].map(keyOf).filter((v, j, a) => v && a.indexOf(v) === j);
          const othersMiss = panelKeys.filter(k => k !== target && (fdOf(k) ? fieldValue(fdOf(k), P0).miss : P0[k] == null || P0[k] === ''));
          if (target) {
            const tel = app.querySelector(`[data-field="${target}"],[data-dk="${target}"],[data-set="${target}"],[data-rqk="${target}"]`);
            if (!visible(tel)) prob('problem', '커서·표시 칸이 안 보임 (' + kind + ')', ex);
            if (!relevant(sig, P0, target, othersMiss)) prob('problem', '엉뚱한 칸: ' + target + ' 를 바꿔도 판정이 안 바뀜 (' + (el.dataset.fix || el.dataset.rq || el.dataset.edit) + ')', ex);
          } else if (S.view === 'onboard' && /^수정$/.test(label)) { prob('note', '내 조건 수정 → 그 단계 열기 ' + el.dataset.edit, ex);
          } else if (S.view === 'onboard') {
            const st = visibleSteps()[S.step], ks = st ? st.f.filter(f => !f.show || f.show(S.profile)).map(f => f.k) : [];
            const miss = ks.filter(k => fieldValue(fdOf(k) || { k, type:'text' }, S.profile).miss), rel = ks.filter(k => relevant(sig, P0, k));
            if (!miss.length && !rel.length) prob('problem', '이동한 단계에 빈칸도 판정을 바꾸는 칸도 없음 (' + el.dataset.edit + ')', ex);
            else prob('note', '단계로만 이동(커서 없음) ' + el.dataset.edit, ex);
          } else if (kind === 'fix' || kind === 'rq') {
            const pn2 = app.querySelector('#fixpanel,#rqpanel');
            if (!pn2) prob('problem', '바로 답하기 칸이 안 열림 (' + kind + ')', ex);
            else if (!pn2.querySelector('[data-field],[data-dk],[data-set],[data-rqk]')) prob('note', '질문 없이 공고문 확인 안내만 (' + (el.dataset.fix || el.dataset.rq) + ')', ex);
            else prob('problem', '커서·빨간 표시 없음 (' + kind + ')', ex);
          }
        }
      }
    }
    return res;
    function hasProfileFor(p){ return p.selfOwn != null || p.household; }
  }, [profiles(), LIM]);
  await b.close();
  out.date = new Date().toISOString().slice(0, 10); out.pageErrors = errs;
  writeFileSync(join(ROOT, 'evidence/qa/input-nav.json'), JSON.stringify(out, null, 1) + '\n');
  const P = Object.entries(out.problems).sort((a, b) => b[1].n - a[1].n);
  console.log(`[QA 입력 버튼] 누른 버튼 ${out.clicks}개 (${Object.entries(out.byKind).map(([k, n]) => k + ' ' + n).join(' · ')}) · 문제 ${P.length}종류` + (errs.length ? ` · 화면 오류 ${errs.length}` : ''));
  P.forEach(([k, v]) => console.log(`  ✗ ${k}: ${v.n}번 · 예 ${JSON.stringify(v.ex[0])}`));
  Object.entries(out.notes).sort((a, b) => b[1].n - a[1].n).slice(0, 12).forEach(([k, v]) => console.log(`  · ${k}: ${v.n}번`));
  process.exit(P.length || errs.length ? 1 : 0);
})();
