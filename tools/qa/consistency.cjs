// 판정 일치 검사 (2026-10-02 사용자 지적 뒤 추가): 같은 공고·같은 내 조건이면 목록 카드(meLine)·상세 맨 위 '내 판정'(rhero)·필터 판정 묶음(eligBucket)이
// 같은 결론(가능 / 확인 필요 / 불가)이어야 한다. 과천 84D 는 카드 '특별공급 확인 필요' · 상세 '신청 불가'로 달랐다 — 판정을 화면마다 따로 계산해서 생긴 문제.
// 지금 공고 전부 × 판정 사례의 서로 다른 내 조건 40개. 사용: NODE_PATH=$(npm root -g) node tools/qa/consistency.cjs → evidence/qa/consistency.json, 다르면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
(async () => {
  const cases = JSON.parse(readFileSync(join(ROOT, 'tests/judge/cases.json'), 'utf8'));
  const profiles = [...new Map(cases.map(c => [JSON.stringify(c.profile), c.profile])).values()].filter((_, i) => i % 3 === 0).slice(0, 40);
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage({ viewport: { width: 390, height: 844 } }); const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(400);
  const out = await page.evaluate(profiles => {
    const cls = h => /st-fail/.test(h.split('</span>')[0]) ? 'fail' : /st-warn/.test(h.split('</span>')[0]) ? 'warn' : /st-ok/.test(h.split('</span>')[0]) ? 'ok' : '?';
    const B = { ok:'ok', unsure:'warn', r2:'warn', no:'fail' };
    const bad = []; let n = 0;
    profiles.forEach((pr, pi) => {
      S.profile = Object.assign({}, DEFAULT_PROFILE, pr); save();
      LISTINGS.filter(L => !L.sample).forEach(L => {
        const card = cls(meLine(L)), bucket = B[eligBucket(L, S.profile)];
        S.view = 'detail'; S.id = L.id; render();
        const h = document.querySelector('.rhero'), hero = h ? (h.className.match(/t-(ok|warn|fail|info)/) || [])[1] : 'none';
        const resFail = eligibility(L, S.profile).items.some(i => i.k === '거주지' && i.s === 'fail'), spOk = spTypesFor(L).some(t => spJudge(L, S.profile, t).s === 'ok');
        n++;
        if (resFail && spOk) bad.push({ id: L.id, name: L.name, profile: pi, card: 'sp-ok', hero, bucket: 'residence-fail', heroText: '거주지 불가인데 특별공급 가능', cardText: '' });
        if (!(card === bucket && hero === bucket)) bad.push({ id: L.id, name: L.name, profile: pi, card, hero, bucket, heroText: h ? h.querySelector('.rbig').textContent : '', cardText: meLine(L).replace(/<[^>]+>/g, '') });
      });
    });
    return { n, bad };
  }, profiles);
  await b.close();
  const by = {}; out.bad.forEach(x => { const k = `카드 ${x.card} / 상세 ${x.hero} / 묶음 ${x.bucket}`; by[k] = (by[k] || 0) + 1; });
  writeFileSync(join(ROOT, 'evidence/qa/consistency.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), checked: out.n, fails: out.bad.length, kinds: by, examples: out.bad.slice(0, 30), pageErrors: errs.slice(0, 5) }, null, 1) + '\n');
  console.log(`[QA 판정 일치] 공고×조건 ${out.n}개 · 카드·상세·묶음 다름 ${out.bad.length}건${errs.length ? ' · 화면 오류 ' + errs.length : ''}`);
  Object.entries(by).forEach(([k, v]) => console.log('  ' + k + ': ' + v));
  out.bad.slice(0, 8).forEach(x => console.log('  ', x.id, x.name.slice(0, 14), '| 카드:', x.cardText.slice(0, 40), '| 상세:', x.heroText));
  process.exit(out.bad.length || errs.length ? 1 : 0);
})();
