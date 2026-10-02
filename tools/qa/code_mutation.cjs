// 코드 변이 검사 (2026-10-02 MASTER QA 12항): 판정·표시 코드에 일부러 오류를 하나씩 넣고(파일은 안 바꾸고 브라우저에 보낼 때만 바꿈)
// 판정 검증 사례(tests/judge/cases.json, 기대값은 tools/make_judge_cases.py 의 독립 계산)와 공급유형 표시 검사가 잡는지 센다.
// 잡지 못한 변이 = 그 규칙을 지키는 테스트가 없다는 뜻. 사용: NODE_PATH=$(npm root -g) node tools/qa/code_mutation.cjs → evidence/qa/code-mutation.json
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
const HTML = readFileSync(join(DOCS, 'index.html'), 'utf8');
const M = [   // [이름, 찾을 글, 바꿀 글]
  ['무주택: 본인 주택을 무시', "if (p.selfOwn && !(exc && OWN_EXC_OK.includes(exc))) own.push('본인 명의 주택');", "if (false) own.push('본인 명의 주택');"],
  ['60㎡ 경계 > → >= (공공 소득·자산 없음 판단)', "if (!pl) return (L.area != null && L.area > 60)", "if (!pl) return (L.area != null && L.area >= 60)"],
  ['60㎡ → 59㎡ (생애최초 단독세대)', "if (alone && (L.area || 0) > 60)", "if (alone && (L.area || 0) > 59)"],
  ['소득 기준 <= → < (공공 일반공급)', "if (m <= spAmt(n, cap)) out.push({ k:'소득 (공공 일반공급)'", "if (m < spAmt(n, cap)) out.push({ k:'소득 (공공 일반공급)'"],
  ['소득 기준 +1%', "if (m <= spAmt(n, cap)) out.push({ k:'소득 (공공 일반공급)'", "if (m <= spAmt(n, cap) * 1.01) out.push({ k:'소득 (공공 일반공급)'"],
  ['혼인 7년 → 8년 (신혼희망타운)', "if (p.marriedOn && p.marriedOn >= addYears(ref, -7)) out.push({ k:'신청 유형 (신혼희망타운)'", "if (p.marriedOn && p.marriedOn >= addYears(ref, -8)) out.push({ k:'신청 유형 (신혼희망타운)'"],
  ['자녀 만 6세 경계 하루 이동', "const kid6 = p.pregnant === true || (p.youngestBirth && p.youngestBirth > addYears(ref, -7));", "const kid6 = p.pregnant === true || (p.youngestBirth && p.youngestBirth >= addYears(ref, -7));"],
  ['거주기간 기준일 <= → <', "if (!R.since || since <= R.since) return { k, s:'ok', v:'해당지역 ('", "if (!R.since || since < R.since) return { k, s:'ok', v:'해당지역 ('"],
  ['통장 가입기간: 규제지역 24 → 12개월', "return [L.regulated ? 24 : L.capital ? 12 : 6, false];", "return [L.regulated ? 12 : L.capital ? 12 : 6, false];"],
  ['예치금 85㎡ 구간 <= → <', "ACCOUNT_DEPOSIT[g][a <= 85 ? 0 :", "ACCOUNT_DEPOSIT[g][a < 85 ? 0 :"],
  ['판정 묶음: 확인 필요를 가능으로', "return e.ok && !e.unsure ? 'ok' : e.ok ? 'unsure'", "return e.ok ? 'ok' : e.ok ? 'unsure'"],
  ['일반 0세대: 특공 0이면 불가 → 확인 필요', "if (u && u.total != null && !u.total) return 'no';", "if (u && u.total != null && !u.total) return 'unsure';"],
  ['마감일 하루 이동', "if (end && TODAY > end) return '마감';", "if (end && TODAY >= end) return '마감';"],
  ['공급유형: 재공급 배지를 무순위로', "/재공급/.test(L.supplyType || L.kind || '') ? '재공급' : '무순위'", "'무순위'"],
  ['공급유형: 일반공급 칸 재공급을 무순위로', "/재공급/.test(L.kind || '') ? '재공급' : '무순위'", "'무순위'"],
];
(async () => {
  const cases = JSON.parse(readFileSync(join(ROOT, 'tests/judge/cases.json'), 'utf8'));
  const listings = JSON.parse(readFileSync(join(ROOT, 'tests/judge/listings.json'), 'utf8'));
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const out = [];
  for (const [name, find, repl] of [['(변이 없음 — 기준선)', '', ''], ...M]) {
    const n = find ? HTML.split(find).length - 1 : 0;
    if (find && n !== 1) { out.push({ name, status: 'NOT_TESTABLE', note: `찾을 글이 ${n}번 나옴 — 코드가 바뀜, 변이 목록 고칠 것` }); continue; }
    const html = find ? HTML.replace(find, repl) : HTML;
    const page = await b.newPage(); const errs = []; page.on('pageerror', e => errs.push(e.message));
    await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
      if (u.pathname === '/' ) return r.fulfill({ status: 200, body: html, contentType: 'text/html' });
      const f = join(DOCS, decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
      r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
    await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
    const r = await page.evaluate(({ cases, listings }) => {
      const byId = Object.fromEntries(listings.map(x => [x.id, fromApi(x)])); let bad = 0;
      for (const c of cases) { const L = byId[c.listing]; S.profile = Object.assign({}, DEFAULT_PROFILE, c.profile); save(); const p = S.profile; let got;
        try {
          if (c.fn === 'score') got = { parts: myScore(L, p).parts.map(x => x.v) };
          else if (c.fn === 'sp') { const q = spJudge(L, p, c.type); got = { s: q.s, ...(c.expect.stage ? { stage: q.stage ? q.stage[0] : null } : {}) }; }
          else if (c.fn === 'acct') { const it = accountItems(L, p) || []; got = { '가입기간': (it.find(i => i.k === '청약통장 가입기간') || {}).s, '예치금': (it.find(i => i.k === '예치금 (민영)') || {}).s }; }
          else if (c.fn === 'pubgen') { const it = pubGeneralItems(L, p); got = { '소득': (it.find(i => i.k.startsWith('소득')) || {}).s }; }
          else if (c.fn === 'town') { const it = townItems(L, p); got = {}; for (const k of Object.keys(c.expect)) got[k] = (it.find(i => i.k === k + ' (신혼희망타운)') || {}).s; }
          else if (c.fn === 'bucket') got = { b: eligBucket(L, p) };
          else if (c.fn === 'item') { const it = c.item === '거주지' ? residenceItem(L, p) : eligibility(L, p).items.find(i => i.k === c.item); got = { s: it ? it.s : 'none' }; }
          else if (c.fn === 'home') { const it = eligibility(L, p).items.find(i => i.k === '무주택 세대') || {}; got = { s: it.s }; }
          else if (c.fn === 'residence') { const q = residenceItem(L, p); got = { s: q.s, v: q.v.includes(c.expect.v) ? c.expect.v : q.v }; }
        } catch (e) { got = { error: e.message }; }
        if (JSON.stringify(got) !== JSON.stringify(c.expect)) bad++; }
      // 공급유형 표시: 불법행위 재공급 주택형의 카드 배지·일반공급 칸 이름에 '무순위'가 나오면 잡힌 것
      const re = LISTINGS.filter(L => /재공급/.test(L.supplyType || '')); let disp = 0;
      re.forEach(L => { const d = document.createElement('div'); d.innerHTML = cardBadges(L); if (/무순위/.test(d.innerText) || genLabel(L) === '무순위') disp++; });
      // 마감 상태: 접수 끝 날짜 = 오늘인 공고는 '접수 중'이어야 한다
      const st = statusOf({ apply: TODAY, applyEnd: TODAY }) === '접수 중' ? 0 : 1;
      return { bad, disp, st };
    }, { cases, listings });
    await page.close();
    const caught = r.bad + r.disp + r.st + errs.length;
    out.push({ name, status: find ? (caught ? 'KILLED' : 'SURVIVED') : (caught ? 'BASELINE_FAIL' : 'BASELINE_OK'), judge_fail: r.bad, display_fail: r.disp, status_fail: r.st, page_errors: errs.length });
    console.log(out[out.length - 1].status.padEnd(14), name, JSON.stringify(r));
  }
  await b.close();
  const mut = out.filter(o => o.name[0] !== '('), killed = mut.filter(o => o.status === 'KILLED').length, surv = mut.filter(o => o.status === 'SURVIVED').length;
  const rep = { date: new Date().toISOString().slice(0, 10), mutations: mut.length, killed, survived: surv, not_testable: mut.filter(o => o.status === 'NOT_TESTABLE').length, score: +(killed / Math.max(1, killed + surv)).toFixed(3), results: out };
  writeFileSync(join(ROOT, 'evidence/qa/code-mutation.json'), JSON.stringify(rep, null, 1) + '\n');
  console.log(`변이 ${mut.length} · 잡음 ${killed} · 못 잡음 ${surv} · 점수 ${rep.score}`);
  process.exit(surv ? 1 : 0);
})();
