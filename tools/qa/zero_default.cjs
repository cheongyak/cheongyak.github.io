// 기본값 0·아니요 칸 점검 (2026-10-06 사용자 '예치금 빈칸을 0원으로' 제보 뒤 '전부 점검').
// 내 조건 중 기본값이 0 이나 false 인 칸(배우자 집·배우자 소득·배우자 대출·재당첨 제한·현금·금융자산·보증금·본인 소득·대출 월 상환)은
// 사용자가 넣었는지(_set)를 따로 기록한다. 넣지 않았으면 '모름'이어야 한다.
// 이 검사: 판정 사례 조건(모든 칸을 넣은 상태)에서 칸 하나를 '넣지 않음'(기본값·_set 에서 뺌)으로 바꾼 결과 r0 와,
//   그 칸에 실제로 있을 법한 값을 넣은 결과들(0 이라고 넣음 포함)을 비교한다.
//   r0 가 단정(가능·불가·2순위만·자금 부족·자금 가능)인데 넣은 값에 따라 결과가 달라지면 = 빈칸을 값으로 본 것 → 위반.
//   (r0 가 '확인 필요'면 통과. 넣은 값이 모두 같은 결과면 그 칸은 결과에 영향이 없어 통과)
// 보는 결과: 일반공급 묶음(eligBucket), 특별공급 유형별(spJudge), 목록 카드 자금(부족/가능), 계약금(contractOk)
// 사용: NODE_PATH=$(npm root -g) node tools/qa/zero_default.cjs → evidence/qa/zero-default.json, 위반이 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
(async () => {
  const cases = JSON.parse(readFileSync(join(ROOT, 'tests/judge/cases.json'), 'utf8'));
  const fx = JSON.parse(readFileSync(join(ROOT, 'tests/judge/listings.json'), 'utf8'));
  const pick = pre => (cases.find(c => c.id.startsWith(pre)) || {}).profile;
  const profiles = ['pub-0', 'min-0', 'rental-0', 'town-0', 'audit-01', 'score-0', 'nw-0', 'first-0'].map(pick).filter(Boolean);
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage(); const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(300);
  const out = await page.evaluate(([profiles, fx]) => {
    const seen = new Set(LISTINGS.map(L => L.id));
    fx.forEach(x => { if (!seen.has(x.id)) LISTINGS.push(fromApi(x)); });
    const byNo = {}; LISTINGS.filter(L => !L.sample).forEach(L => { const k = L.id.split('-')[0]; (byNo[k] = byNo[k] || []).push(L); });
    const Ls = Object.values(byNo).flatMap(a => { const s = a.slice().sort((x, y) => (x.area || 0) - (y.area || 0)); return [...new Set([s[0], s[s.length - 1]])]; });
    const ALT = { spouseOwn: [true, false], spouseIncome: [0, 3000, 9000], spouseLoan: [0, 150], recentWin: [true, false], cashGroup: [0, 3000, 30000, 150000], income: [0, 2500, 6000, 15000], loanMonthly: [0, 150, 400], acctAmount: [0, 200, 1500] };
    const card = (L, p) => { const s = p; const o = {}; try { o.b = eligBucket(L, s); spTypesFor(L).forEach(t => { o['sp:' + t] = spJudge(L, s, t).s; }); } catch (e) { o.err = e.message; }
      if (!isRental(L) && !genNone(L)) { try { const f = funding(L, s, planOpt(L)), g = bestGap(f, planOpt(L)); o.fund = g > 0 ? (f.unk ? 'warn' : 'short') : 'ok'; o.contract = f.contractOk ? 'ok' : f.contractOk == null ? 'warn' : 'short';   /* 화면: 부족(빨강)·가능(초록)·입력 필요(warn) */ } catch (e) {} }
      return o; };
    const decisive = (k, v) => !['unsure', 'warn'].includes(v);
    const V = {}; let n = 0;
    profiles.forEach((pr, pi) => {
      const base = Object.assign({}, DEFAULT_PROFILE, pr); base._set = [...new Set([...(pr._set || []), ...ZERO_KEYS])];
      if (base.married !== true) base.married = true;   // 배우자 칸을 보려면 혼인 중
      if (!base.marriedOn) base.marriedOn = '2022-01-01';
      Object.keys(ALT).forEach(k => {
        if (k === 'recentWin' && base.everWin === 'none') return;   // 당첨 이력 '없음'이라고 답했으면 재당첨 제한은 아님(syncV2) — 빈칸이 아니다
        // 현금·금융자산·보증금은 같은 입력 단계의 세 칸 — 셋 다 비웠을 때를 본다(하나라도 넣었으면 나머지 빈칸은 0 으로 봄). 값은 현금 칸에 넣는다
        const KS = k === 'cashGroup' ? ['cash', 'liquid', 'deposit'] : [k], K0 = KS[0];
        const p0 = Object.assign({}, base, Object.fromEntries(KS.map(x => [x, DEFAULT_PROFILE[x]])), { _set: base._set.filter(x => !KS.includes(x)) });
        Ls.forEach(L => { n++;
          const r0 = card(L, p0), alts = ALT[k].map(v => card(L, Object.assign({}, base, Object.fromEntries(KS.map(x => [x, x === K0 ? v : 0])), { _set: [...new Set([...base._set, ...KS])] })));
          Object.keys(r0).forEach(key => { if (key === 'err' || !decisive(key, r0[key])) return;
            const vals = new Set(alts.map(a => a[key]));
            if (vals.size > 1) { const id = k + ' → ' + key; (V[id] = V[id] || { n: 0, ex: [] }).n++; if (V[id].ex.length < 3) V[id].ex.push({ L: L.id, prof: pi, unentered: r0[key], withValues: ALT[k].map((v, i) => v + ':' + alts[i][key]).join(' ') }); }
          });
        });
      });
    });
    return { checks: n, profiles: profiles.length, listings: Ls.length, violations: V };
  }, [profiles, fx]);
  await b.close();
  out.date = new Date().toISOString().slice(0, 10); out.pageErrors = errs;
  writeFileSync(join(ROOT, 'evidence/qa/zero-default.json'), JSON.stringify(out, null, 1) + '\n');
  const kinds = Object.keys(out.violations);
  console.log(`[QA 기본값 0 칸] 조건 ${out.profiles}개 × 공고 ${out.listings}개 × 칸 9 · 검사 ${out.checks}회 (현금·금융·보증금은 한 묶음) · 빈칸을 값으로 본 곳 ${kinds.length}종류` + (errs.length ? ` · 화면 오류 ${errs.length}` : ''));
  kinds.forEach(k => console.log(`  ${k}: ${out.violations[k].n}건 · 예 ${JSON.stringify(out.violations[k].ex[0])}`));
  process.exit(kinds.length || errs.length ? 1 : 0);
})();
