// 특별공급 칸 문구 일치 검사 (2026-10-02, 공공임대 특공 작업 중 발견한 두 가지 표시 오류의 재발 방지)
//  1) 뽑는 방식: 같은 판정 결과로 만든 한 줄 요약(spHeadPlain·spHeadline)·설명(spHowPlain)·내 위치(spPosition·spMinePlain)가 서로 같은 방식을 말해야 한다.
//     공공 신혼부부 2단계(일반공급)는 '선정순위 → 추첨'(2026000409 「선정순위에 따라 … 경쟁이 있는 경우 추첨」)인데 한 줄 요약만 '점수 순'이라고 했다.
//     공공 신혼부부 1단계·신생아 1·2단계는 점수 순, 생애최초·추첨 단계는 추첨(점수 없음).
//  2) 단계 세대수: '약 N세대'가 공고문 배분과 같아야 한다 — 공공은 '주택형별 공급량의 70%(소수점 이하는 올림)', 앞 단계부터, 마지막은 잔여물량.
//     공공 노부모부양 우선공급은 90%인데 70%로 계산했고, 단계마다 반올림해 3세대 70%(실제 3세대)를 2세대로 보였다.
//  기대값은 이 파일의 표(공고문 비율)로 따로 계산한다 — 화면의 spStageUnits 를 쓰지 않는다.
// 판정 사례(tests/judge/cases.json)의 특별공급 사례 조건 × 그 공고 × 유형 물량 1~12세대. 사용: NODE_PATH=$(npm root -g) node tools/qa/sp_text.cjs → evidence/qa/sp-text.json, 다르면 종료 코드 1
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
// 공고문 단계 비율 (공공 2026000409·414 당첨자 선정방법, 민영 2026000103·443). 마지막 단계는 잔여물량
const SHARES = {
  public: { newborn: [['우선공급', 70], ['일반공급', 20], ['추첨', null]], newlywed: [['우선공급', 70], ['일반공급', 20], ['추첨', null]],
            first: [['우선공급', 70], ['일반공급', 20], ['추첨', null]], multichild: [['우선공급 (배점순)', 90], ['추첨', null]], elder: [['우선공급', 90], ['추첨', null]] },
  minyoung: { newborn: [['우선공급', 50], ['일반공급', 20], ['추첨', null]], newlywed: [['우선공급', 50], ['일반공급', 20], ['추첨', null]], first: [['우선공급', 50], ['일반공급', 20], ['추첨', null]] },
};
function expectUnits(pub, type, stage, u){
  const st = (SHARES[pub ? 'public' : 'minyoung'][type] || []); let left = u;
  for (let k = 0; k < st.length; k++) { const v = st[k][1] == null ? left : Math.min(left, pub ? Math.ceil(u * st[k][1] / 100) : Math.round(u * st[k][1] / 100));
    if (st[k][0] === stage) return Math.max(0, v); left -= v; }
  return null;
}
// 뽑는 방식 (공고문): score = 점수 순, lottery = 점수 없음
function expectMethod(pub, type, stage){
  if (!stage || /추첨/.test(stage)) return 'lottery';
  if (pub && type === 'newborn') return 'score';
  if (pub && type === 'newlywed') return stage === '우선공급' ? 'score' : 'lottery';
  if (type === 'newborn' || type === 'newlywed' || type === 'first') return 'lottery';
  return null;   // 다자녀(배점)·노부모(저축액·가점)는 여기서 보지 않는다
}
(async () => {
  const cases = JSON.parse(readFileSync(join(ROOT, 'tests/judge/cases.json'), 'utf8')).filter(c => c.fn === 'sp');
  const fx = JSON.parse(readFileSync(join(ROOT, 'tests/judge/listings.json'), 'utf8'));
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage(); const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(300);
  const rows = await page.evaluate(([cases, fx]) => {
    const strip = h => String(h || '').replace(/<[^>]+>/g, '');
    const out = [];
    for (const c of cases) {
      const raw = fx.find(x => x.id === c.listing); if (!raw) continue;
      for (let u = 1; u <= 12; u++) {
        const L = fromApi(raw); L.specialUnits = Object.assign({}, L.specialUnits || {}, { [c.type]: u, total: (L.specialUnits && L.specialUnits.total) || u });
        const p = Object.assign({}, DEFAULT_PROFILE, c.profile), r = spJudge(L, p, c.type);
        if (r.s !== 'ok') continue;
        const t = { head: spHeadPlain(L, p, r).t, line: spHeadline(L, p, r).text, how: spHowPlain(L, p, r), pos: strip(spPosition(L, p, r)), mine: strip(spMinePlain(L, p, r)) };
        out.push({ id: c.id, listing: c.listing, type: c.type, pub: r.pub, stage: r.stage && r.stage[0], u, t });
      }
    }
    return out;
  }, [cases, fx]);
  await b.close();
  const bad = [];
  for (const x of rows) {
    const m = expectMethod(x.pub, x.type, x.stage);
    if (m) for (const k of ['head', 'line', 'how']) {
      const saysScore = /점수 순|점수\(최대|^점수 \d|점수가 높은 순/.test(x.t[k]);
      if (m === 'lottery' && saysScore) bad.push({ ...x, why: `${k}: 공고문은 점수 없이 뽑는데 '점수'라고 함`, text: x.t[k] });
      if (m === 'score' && k !== 'line' && !/점수/.test(x.t[k])) bad.push({ ...x, why: `${k}: 공고문은 점수 순인데 점수 언급 없음`, text: x.t[k] });
    }
    const want = expectUnits(x.pub, x.type, x.stage, x.u);
    for (const k of ['line', 'pos', 'mine']) {
      const g = /약 (\d+)세대/.exec(x.t[k]);
      if (g && want != null && +g[1] !== want) bad.push({ ...x, why: `${k}: 약 ${g[1]}세대 ≠ 공고문 배분 ${want}세대 (물량 ${x.u})`, text: x.t[k] });
    }
  }
  const by = {}; bad.forEach(x => { const k = x.why.replace(/\d+/g, 'N').slice(0, 60); by[k] = (by[k] || 0) + 1; });
  writeFileSync(join(ROOT, 'evidence/qa/sp-text.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), checked: rows.length, fails: bad.length, kinds: by,
    examples: bad.slice(0, 20).map(x => ({ id: x.id, type: x.type, stage: x.stage, u: x.u, why: x.why, text: x.text })), pageErrors: errs.slice(0, 5) }, null, 1) + '\n');
  console.log(`[QA 특공 문구] 판정 '가능' 칸 ${rows.length}개 · 방식·세대수 다름 ${bad.length}건${errs.length ? ' · 화면 오류 ' + errs.length : ''}`);
  Object.entries(by).forEach(([k, v]) => console.log('  ' + k + ': ' + v));
  bad.slice(0, 6).forEach(x => console.log('  ', x.id, x.type, x.stage, 'u=' + x.u, '|', x.why, '|', String(x.text).slice(0, 60)));
  process.exit(bad.length || errs.length ? 1 : 0);
})();
