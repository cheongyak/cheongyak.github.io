// 판정 단조성 검사 (2026-10-02 사용자 QA '확인 필요 → 가능' · 경계값 · '지원하지 않는 유형 → 가능' 재발 방지).
// 사례를 손으로 고르지 않고, 지금 공고 + 판정 사례 고정 공고 전부에 대해 두 성질을 본다.
//  A. 정보 단조성: 내 조건 칸 하나를 비우거나(답 안 함) 공고 조건 하나를 모르게 하면(수집이 못 읽음) 결과가 '가능'으로 새로 바뀌면 안 된다.
//     모르는 것이 늘어나는데 확신이 늘면 '확인 필요 → 가능' 오판이다. (특별공급 결과도 같은 규칙)
//  B. 값 단조성: 소득·부동산·자동차·총자산이 커지면 결과가 좋아지면 안 되고, 통장 가입기간·납입 횟수·예치금·저축액·거주기간이 길어지면 나빠지면 안 된다.
//     혼인 기간·막내 나이가 늘면 신혼부부·신생아(·신혼희망타운) 결과가 좋아지면 안 된다. 경계 앞·위·뒤에서 결과가 되돌아가면(가능→불가→가능) 걸린다.
// 순위: 가능 2 > 확인 필요·2순위 1 > 불가 0. 사용: NODE_PATH=$(npm root -g) node tools/qa/monotonic.cjs → evidence/qa/monotonic.json, 위반이 있으면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
(async () => {
  const cases = JSON.parse(readFileSync(join(ROOT, 'tests/judge/cases.json'), 'utf8'));
  const fx = JSON.parse(readFileSync(join(ROOT, 'tests/judge/listings.json'), 'utf8'));
  const pick = pre => (cases.find(c => c.id.startsWith(pre)) || {}).profile;
  const profiles = ['pub-0', 'min-0', 'rental-0', 'town-0', 'audit-01', 'score-0'].map(pick).filter(Boolean);
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage(); const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(300);
  const out = await page.evaluate(([profiles, fx]) => {
    const seen = new Set(LISTINGS.map(L => L.id));
    fx.forEach(x => { if (!seen.has(x.id)) LISTINGS.push(fromApi(x)); });
    // 같은 공고에서 면적대가 다른 주택형 2개까지 (규칙은 공고 단위, 면적 기준만 주택형마다 다름)
    const byNo = {}; LISTINGS.filter(L => !L.sample).forEach(L => { const k = L.id.split('-')[0]; (byNo[k] = byNo[k] || []).push(L); });
    const Ls = Object.values(byNo).flatMap(a => { const s = a.slice().sort((x, y) => (x.area || 0) - (y.area || 0)); return [...new Set([s[0], s[s.length - 1]])]; });
    const RB = { ok:2, unsure:1, r2:1, no:0 }, RS = { ok:2, warn:1, fail:0 };
    const res = (L, p) => { const o = { b: eligBucket(L, p) }; spTypesFor(L).forEach(t => { o[t] = spJudge(L, p, t).s; }); return o; };
    const rank = (k, v) => k === 'b' ? RB[v] : RS[v];
    const V = []; let nA = 0, nB = 0;
    const blank = v => typeof v === 'boolean' || v === false ? null : typeof v === 'number' ? null : typeof v === 'string' ? '' : null;
    const PKEYS = Object.keys(DEFAULT_PROFILE).filter(k => !/^(cash|liquid|deposit|loanMonthly|spouseLoan|family)$/.test(k));   // 자금 칸은 자격에 안 씀
    const LKEYS = ['pubLimits', 'residence', 'specialUnits', 'needHead', 'houseDtl', 'regulated', 'priceCap', 'mcQuota', 'scoreRatio', 'accountMonths', 'depositCount', 'residenceDuty', 'notice'];
    profiles.forEach((pr, pi) => { const base = Object.assign({}, DEFAULT_PROFILE, pr);
      Ls.forEach(L => { const r0 = res(L, base);
        // A1. 내 조건 칸 하나 비우기
        PKEYS.forEach(k => { if (base[k] == null || base[k] === '') return; nA++;
          const p = Object.assign({}, base, { [k]: blank(base[k]) }), r1 = res(L, p);
          Object.keys(r1).forEach(t => { if (r1[t] && rank(t, r1[t]) === 2 && rank(t, r0[t]) < 2) {
            // 허용 예외: 원래 '확인 필요'가 입력끼리 모순이라서였으면(예: '부모님 3년 부양 예' + '같은 등본 부모 0명') 모순된 칸을 비우면 풀리는 게 맞다
            if (t !== 'b' && spJudge(L, base, t).warn.some(w => /입력했어요/.test(w))) return;
            V.push({ kind:'정보↓ 가능↑', id:L.id, name:L.name, profile:pi, field:'내 조건 ' + k, from:base[k], what:t, before:r0[t], after:r1[t] }); } }); });
        // A2. 공고 조건 하나 모르게 하기 (수집이 못 읽은 경우)
        LKEYS.forEach(k => { if (L[k] == null) return; nA++;
          const L2 = Object.assign(Object.create(Object.getPrototypeOf(L)), L, { [k]: null }), r1 = res(L2, base);
          Object.keys(r1).forEach(t => { if (r0[t] == null) return; if (rank(t, r1[t]) === 2 && rank(t, r0[t]) < 2) V.push({ kind:'정보↓ 가능↑', id:L.id, name:L.name, profile:pi, field:'공고 ' + k, what:t, before:r0[t], after:r1[t] }); }); });
      }); });
    // B. 값 단조성 (조건 3개 × 공고 전부)
    const ymd = d => d.toISOString().slice(0, 10), before = (L, n) => { const d = new Date((L.notice || TODAY) + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() - 1); d.setUTCMonth(d.getUTCMonth() - n); return ymd(d); }, mback = n => { const d = new Date(TODAY + 'T00:00:00Z'); d.setUTCMonth(d.getUTCMonth() - n); return ymd(d); };
    const SW = [
      ['소득↑ 나빠지기만', 'down', n => ({ hhIncomeYear: n * 400, income: n * 400 }), 50],
      ['부동산↑ 나빠지기만', 'down', n => ({ realEstate: n * 1500 }), 40],
      ['자동차↑ 나빠지기만', 'down', n => ({ carValue: n * 300 }), 30],
      ['금융자산↑ 나빠지기만', 'down', n => ({ cash: n * 2000, townFinOther: n * 500 }), 30],
      ['통장 가입기간↑ 좋아지기만', 'up', n => ({ acctSince: mback(n * 3) }), 50],
      ['납입 횟수↑ 좋아지기만', 'up', n => ({ acctCount: n * 3 }), 50],
      ['예치금↑ 좋아지기만', 'up', n => ({ acctAmount: n * 50 }), 40],
      ['저축액↑ 좋아지기만', 'up', n => ({ acctPaid: n * 50 }), 40],
      ['거주기간↑ 좋아지기만', 'up', (n, L) => { const d = before(L, n * 2); return { sidoSince: d, areaSince: d, sidoOwnSince: d }; }, 40],   // 공고일 전 전입만 — 공고일 뒤 전입은 '그때 주소 모름'(확인 필요)이 맞다
      ['혼인기간↑ 신혼 결과 나빠지기만', 'down', n => ({ marriedOn: mback(n * 3) }), 40, ['newlywed']],
      ['막내 나이↑ 신생아 결과 나빠지기만', 'down', n => ({ youngestBirth: mback(n * 2), pregnant: false }), 40, ['newborn']],
    ];
    profiles.slice(0, 3).forEach((pr, pi) => { const base = Object.assign({}, DEFAULT_PROFILE, pr);
      Ls.forEach(L => SW.forEach(([name, dir, f, steps, only]) => {
        const seq = []; for (let n = 0; n <= steps; n++) { nB++; seq.push([n, res(L, Object.assign({}, base, f(n, L)))]); }
        const keys = Object.keys(seq[0][1]).filter(t => !only || only.includes(t));
        keys.forEach(t => { let best = null, bad = null;
          for (const [n, r] of seq) { const v = rank(t, r[t]); if (v == null) continue;
            if (best != null && (dir === 'down' ? v > best.v : v < best.v)) { bad = { n, v: r[t], prev: best }; break; }
            if (best == null || (dir === 'down' ? v < best.v : v > best.v)) best = { n, v, s: r[t] }; }
          if (bad) V.push({ kind:'값 단조성', id:L.id, name:L.name, profile:pi, field:name, what:t, at: JSON.stringify(f(bad.n, L)), back:bad.v, after: JSON.stringify(f(bad.prev.n, L)) + ' 에서 ' + bad.prev.s }); });
      })); });
    return { V, nA, nB, nL: Ls.length };
  }, [profiles, fx]);
  await b.close();
  const by = {}; out.V.forEach(x => { const k = x.kind + ' · ' + x.field + ' · ' + x.what; by[k] = (by[k] || 0) + 1; });
  writeFileSync(join(ROOT, 'evidence/qa/monotonic.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), listings: out.nL, profiles: profiles.length,
    info_checks: out.nA, value_points: out.nB, violations: out.V.length, kinds: by, examples: out.V.slice(0, 60), pageErrors: errs.slice(0, 5) }, null, 1) + '\n');
  console.log(`[QA 단조성] 공고 ${out.nL}개 × 조건 ${profiles.length}개 · 정보 줄이기 ${out.nA}회 · 값 바꾸기 ${out.nB}회 · 위반 ${out.V.length}건${errs.length ? ' · 화면 오류 ' + errs.length : ''}`);
  Object.entries(by).sort((a, b) => b[1] - a[1]).slice(0, 15).forEach(([k, n]) => console.log('  ' + k + ': ' + n));
  out.V.slice(0, 10).forEach(x => console.log('   ', x.id, (x.name || '').slice(0, 12), '|', x.field, x.what, x.before ? x.before + '→' + x.after : '', x.at ? 'at ' + x.at + ' → ' + x.back + ' (' + x.after + ')' : ''));
  process.exit(out.V.length || errs.length ? 1 : 0);
})();
