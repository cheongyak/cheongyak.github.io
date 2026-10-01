// 변이(mutation)·단조성 검사 (2026-10-01 판정엔진 감사): 프로필의 값 하나만 바꿨을 때 판정이 '말이 되는 방향'으로만 움직이는지 본다.
// 기대값을 화면 코드로 정하지 않는다 — 규칙의 방향(집이 생기면 유리해질 수 없다 등)만 검사하므로 독립적인 검사다.
// 사용: NODE_PATH=... node tools/qa/mutation.cjs [프로필 수(기본 300)] [시드]
// 결과: 표준 출력 요약, 위반이 있으면 종료 코드 1 · 자세한 목록은 /tmp/mutation-report.json
const { chromium } = require('playwright');
const { readFileSync, existsSync, writeFileSync } = require('node:fs'); const { join, extname } = require('node:path');
const dir = join(__dirname, '..', '..', 'docs'), N = +process.argv[2] || 300, SEED = +process.argv[3] || 7;
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined }); const p = await b.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'site.local') return r.abort();
    const f = join(dir, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!existsSync(f)) return r.fulfill({ status: 404, body: '' }); r.fulfill({ status: 200, body: readFileSync(f), contentType: extname(f) === '.html' ? 'text/html' : 'application/json' }); });
  await p.goto('http://site.local/', { waitUntil: 'networkidle' }); await p.waitForTimeout(600);
  const res = await p.evaluate(([N, SEED]) => {
    let s = SEED; const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648;
    const pick = a => a[Math.floor(rnd() * a.length)], int = (a, b) => a + Math.floor(rnd() * (b - a + 1));
    const day = (y0, y1) => `${int(y0, y1)}-${String(int(1, 12)).padStart(2, '0')}-${String(int(1, 28)).padStart(2, '0')}`;
    const lst = LISTINGS.filter(L => !L.sample);
    // 판정 순위: 가능 > 확인 필요 > 2순위만 > 불가 / 특별공급: ok > warn > fail
    const RANK = { ok: 3, unsure: 2, r2: 1, no: 0 }, SR = { ok: 2, warn: 1, fail: 0 };
    const viol = [], tally = {};
    const MUT = [   // [이름, 바꾸기, 방향: 'notBetter' = 바꾼 뒤가 더 유리하면 위반, 'notWorse' = 더 불리하면 위반, 적용 조건]
      ['본인 주택 없음→있음', P => Object.assign(P, { selfOwn: true, hhHomes: P.hhHomes === '0' || !P.hhHomes ? '1' : '2+', hhNeverOwned: false }), 'notBetter'],
      ['세대 주택 0→1(그 밖의 세대원)', P => Object.assign(P, { hhHomes: '1', hhOwner: 'other', hhNeverOwned: false }), 'notBetter', P => P.hhHomes === '0' && !P.selfOwn],
      ['세대 소득 +50%', P => Object.assign(P, { hhIncomeYear: Math.round((P.hhIncomeYear || 0) * 1.5) + 100, income: Math.round((P.income || 0) * 1.5) + 100 }), 'notBetter'],
      ['부동산 +1억', P => Object.assign(P, { realEstate: (P.realEstate || 0) + 10000 }), 'notBetter'],
      ['자동차 +2천만', P => Object.assign(P, { carValue: (P.carValue || 0) + 2000 }), 'notBetter'],
      ['재당첨 제한 중', P => Object.assign(P, { everWin: 'yes', win5y: true, recentWin: true }), 'notBetter'],
      ['세대주→세대원', P => Object.assign(P, { household: 'parents', headSince: '', parentsOwn: false, parents60: true }), 'notBetter', P => P.household === 'head'],
      ['통장 가입일 5년 앞당김', P => Object.assign(P, { acctSince: P.acctSince ? (Number(P.acctSince.slice(0, 4)) - 5) + P.acctSince.slice(4) : P.acctSince }), 'notWorse', P => !!P.acctSince],
      ['예치금 +1,000만', P => Object.assign(P, { acctAmount: (P.acctAmount || 0) + 1000 }), 'notWorse'],
      ['납입 횟수 +24회', P => Object.assign(P, { acctCount: (P.acctCount || 0) + 24 }), 'notWorse', P => P.acctCount != null],
      ['통장 있음→없음', P => Object.assign(P, { acctType: 'none' }), 'notBetter', P => P.acctType && P.acctType !== 'none'],
      ['5년 내 당첨', P => Object.assign(P, { everWin: 'yes', win5y: true, recentWin: false }), 'notBetter'],
    ];
    const scoreMut = [   // 가점은 값이 커지거나 그대로여야 하는 변경
      ['부양가족 +1', P => Object.assign(P, { dependents: (P.dependents || 0) + 1 }), 1],
      ['통장 가입일 1년 앞당김', P => Object.assign(P, { acctSince: P.acctSince ? (Number(P.acctSince.slice(0, 4)) - 1) + P.acctSince.slice(4) : P.acctSince }), 1],
      ['본인 주택 생김', P => Object.assign(P, { selfOwn: true }), -1],
    ];
    const verdict = (L, P) => eligBucket(L, P);
    for (let i = 0; i < N; i++) {
      const L = pick(lst), married = rnd() < 0.6, kids = married ? pick([0, 1, 2, 3]) : pick([0, 0, 0, 1]);
      const base = { homeSido: rnd() < 0.6 ? L.sido : pick(['서울', '경기', '인천', '부산', '충남']), homeSigun: L.sigungu || '', sidoOwnSince: day(2005, 2023), household: pick(['head', 'head', 'parents']),
        selfOwn: false, married, marriedOn: married ? day(2014, 2025) : '', spouseOwn: false, acctType: pick(['all', 'all', 'deposit', 'saving']), acctSince: day(2006, 2025), acctAmount: pick([200, 300, 600, 1500]),
        acctCount: int(6, 120), acctPaid: pick([300, 900, 2000]), hhHomes: '0', everWin: 'none', win5y: false, recentWin: false, birth: day(1970, 1999), dependents: married ? 1 + kids : 0,
        kidsMinor: kids, youngestBirth: kids ? day(2016, 2026) : '', pregnant: false, hhSize: (married ? 2 : 1) + kids, kidsOnDeed: kids, eldersOnDeed: 0, income: pick([3000, 5000, 7000]),
        spouseIncome: married ? pick([0, 3000]) : 0, realEstate: pick([0, 0, 15000]), carValue: pick([0, 2000]), hhNeverOwned: true, taxYears5: true, elder65: false, townType: married ? null : pick(['pre', 'single', 'none']),
        townInsurance: 0, townFinOther: 0, townOtherAsset: 0, townDebt: 0, cash: 3000, headSince: '2015-01-01' };
      base.areaSince = base.sidoOwnSince; base.sidoSince = base.sidoOwnSince; base.hhIncomeYear = base.income + base.spouseIncome;
      const P0 = Object.assign({}, DEFAULT_PROFILE, base); syncHome(P0);
      const v0 = verdict(L, P0), types = spTypesFor(L), sp0 = types.map(t => spJudge(L, P0, t).s);
      for (const [name, f, dirn, cond] of MUT) {
        if (cond && !cond(P0)) continue;
        const P1 = f(Object.assign({}, P0)); syncHome(P1);
        const v1 = verdict(L, P1), sp1 = types.map(t => spJudge(L, P1, t).s);
        tally[name] = (tally[name] || 0) + 1;
        const worse = (a, b) => dirn === 'notBetter' ? b > a : b < a;
        if (worse(RANK[v0], RANK[v1])) viol.push({ mut: name, listing: L.id, what: '일반공급', from: v0, to: v1, base });
        // 허용 예외: 생애최초 '단독세대주'만 전용 60㎡ 이하(규칙 제43조③ 후단) — 세대원이 되면 면적 제한이 풀리는 것이 규칙대로다
        const allowed = t => t === 'first' && name === '세대주→세대원' && P0.hhSize === 1 && (L.area || 0) > 60;
        types.forEach((t, k) => { if (!allowed(t) && worse(SR[sp0[k]], SR[sp1[k]])) viol.push({ mut: name, listing: L.id, what: '특별공급 ' + t, from: sp0[k], to: sp1[k], base }); });
      }
      if (L.houseDtl !== '국민') {
        const s0 = myScore(L, P0).total;
        for (const [name, f, sign] of scoreMut) {
          const P1 = f(Object.assign({}, P0)); syncHome(P1); const s1 = myScore(L, P1).total; tally['가점: ' + name] = (tally['가점: ' + name] || 0) + 1;
          if (s0 != null && s1 != null && (sign > 0 ? s1 < s0 : s1 > s0)) viol.push({ mut: '가점: ' + name, listing: L.id, what: '가점', from: s0, to: s1, base });
        }
      }
    }
    return { tally, viol };
  }, [N, SEED]);
  writeFileSync('/tmp/mutation-report.json', JSON.stringify(res, null, 1));
  const total = Object.values(res.tally).reduce((a, x) => a + x, 0);
  console.log(`[변이 검사] 변경 ${total}건 (프로필 ${N}개) · 위반 ${res.viol.length}건` + (errs.length ? ' · 화면 오류 ' + errs.length : ''));
  const by = {}; res.viol.forEach(v => { by[v.mut + ' · ' + v.what + ' ' + v.from + '→' + v.to] = (by[v.mut + ' · ' + v.what + ' ' + v.from + '→' + v.to] || 0) + 1; });
  Object.entries(by).sort((a, b) => b[1] - a[1]).forEach(([k, n]) => console.log('  ' + n + ' · ' + k));
  await b.close(); process.exit(res.viol.length || errs.length ? 1 : 0);
})();
