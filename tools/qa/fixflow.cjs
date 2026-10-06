// '바로 답하기'(inline_fix) 흐름 검사: 무작위·빈 프로필로 공고 상세의 모든 '바로 답하기' 버튼을 눌러, 나온 질문에 답하면
// 그 항목이 '확인 필요'에서 벗어나는지(판정되는지) 센다. 답한 뒤에도 남으면 항목·값을 출력한다 → 질문 연결이 빠진 곳.
// 사용: NODE_PATH=... node tools/qa/fixflow.cjs [프로필 수=8] [시드]
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs'); const { join, extname } = require('node:path');
const dir = join(__dirname, '../../docs'), N = +process.argv[2] || 8, SEED = +process.argv[3] || 77;
(async () => {
  const b = await chromium.launch(existsSync('/opt/pw-browsers/chromium') ? { executablePath: '/opt/pw-browsers/chromium' } : {});
  const p = await b.newPage({ viewport: { width: 390, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.abort();
    const f = join(dir, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: readFileSync(f), contentType: extname(f) === '.html' ? 'text/html' : 'application/json' }); });
  await p.goto('http://site.local/', { waitUntil: 'networkidle' }); await p.waitForTimeout(600);
  const res = await p.evaluate(async ([N, SEED]) => {
    let s = SEED; const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648, pick = a => a[Math.floor(rnd() * a.length)];
    const full = { homeSido:'경기', homeSigun:'광명시', sidoOwnSince:'2015-01-01', areaSince:'2015-01-01', household:'head', headSince:'2016-01-01', selfOwn:false, married:true, marriedOn:'2022-05-01', spouseOwn:false,
      acctType:'all', acctSince:'2014-01-01', acctAmount:1500, acctCount:60, acctPaid:1500, hhHomes:'0', everWin:'none', win5y:false, recentWin:false, birth:'1990-01-01', dependents:2, kidsMinor:1, youngestBirth:'2025-01-01',
      pregnant:false, hhSize:3, kidsOnDeed:1, eldersOnDeed:0, income:5000, spouseIncome:3000, hhIncomeYear:8000, realEstate:0, carValue:1500, hhNeverOwned:true, taxYears5:true, elder65:false, cash:20000 };
    const profs = [{ homeSido:'경기', homeSigun:'광명시', household:'head', selfOwn:false }, { hhHomes:'1', selfOwn:false, household:'head', homeSido:'인천', homeSigun:'계양구' }];
    for (let i = 0; i < N; i++) { const q = {}; Object.keys(full).forEach(k => { if (rnd() < 0.6) q[k] = full[k]; }); q.homeSido = pick(['서울','경기','인천','부산']); profs.push(q); }
    const answer = fd => fd.type === 'choice' ? fd.o[0][0] : fd.type === 'date' ? '2015-01-01' : fd.type === 'text' ? '성남시' : fd.type === 'count' ? 30 : 3000;
    const out = { opened:0, resolved:0, still:{}, noField:{} };
    const LS = LISTINGS.filter(L => !L.sample && L.category === 'general');
    for (const pr of profs) for (const L of LS.filter((_, j) => j % 3 === 0)) {
      try { localStorage.clear(); } catch (e) {}
      S.profile = Object.assign({}, DEFAULT_PROFILE, pr); syncHome(S.profile); save(); S.id = L.id; S.fix = null; go('detail');
      const keys = [...document.querySelectorAll('[data-fix]')].map(x => x.dataset.fix);
      for (const k of [...new Set(keys)]) {
        S.profile = Object.assign({}, DEFAULT_PROFILE, pr); syncHome(S.profile); save();
        S.fix = { id:L.id, k, keys: fixKeysFor(k, L, S.profile) }; render(); out.opened++;
        for (let round = 0; round < 6; round++) {   // 답하면 새 질문이 열릴 수 있어 여러 번
          const fds = []; S.fix.keys.forEach(kk => { const fd = fieldVariants(kk).find(f => !f.show || f.show(S.profile)); if (fd && (S.profile[fd.k] == null || S.profile[fd.k] === '' || !entered(S.profile, fd.k))) fds.push(fd); });   // 기본값 0·아니요 칸도 넣지 않았으면 답함 (2026-10-06)
          if (!fds.length) break; fds.forEach(fd => { S.profile[fd.k] = answer(fd); markSet(S.profile, fd.k, true); }); save(); render();
        }
        if (!document.querySelector('#fixpanel .field') && !document.querySelector('#fixpanel .muted')) (out.noField[k] = (out.noField[k] || 0) + 1);
        const st = document.querySelector('#fixpanel .fixstat'); const txt = st ? st.innerText : '';
        if (/판정됐어요/.test(txt)) out.resolved++; else { const kk = k + ' → ' + txt.split('\n')[0].slice(0, 60); out.still[kk] = (out.still[kk] || 0) + 1; }
      }
    }
    return out;
  }, [N, SEED]);
  console.log('열어 본 버튼', res.opened, '· 답한 뒤 판정됨', res.resolved);
  Object.entries(res.still).sort((a, b) => b[1] - a[1]).forEach(([k, n]) => console.log('  남음', n, k));
  if (Object.keys(res.noField).length) console.log('질문 없음', res.noField);
  console.log('오류', errs.length, errs.slice(0, 3)); await b.close();
})();
