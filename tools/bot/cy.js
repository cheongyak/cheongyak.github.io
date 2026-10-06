// 청약봇 답변용 (스킬 cheongyak-bot-answer, 2026-10-06 사용자 '다른 세션에서도 청약봇에 접근해 ai 답변 전달받을수잇게'):
// docs/index.html 의 판정 엔진을 화면 없이 Node 에서 실행해 공고별 판정·특공·가점·마진·자금을 JSON 으로 낸다. 저장소 파일은 바꾸지 않는다.
// 사용: node tools/bot/cy.js docs '<조건 JSON>' [--ids id1,id2] [--sido 서울] [--name 검색어] [--all]
//       node tools/bot/cy.js docs '<조건 JSON>' --rental [--youth] [--sido 서울] [--name 검색어]   ← LH 공공임대·청년 주택 (계층별 판정)
const fs = require('fs'), vm = require('vm');
const [DOCS, PJSON = '{}', ...rest] = process.argv.slice(2);
const opt = {}; for (let i = 0; i < rest.length; i++) if (rest[i].startsWith('--')) opt[rest[i].slice(2)] = rest[i + 1] && !rest[i + 1].startsWith('--') ? rest[++i] : true;
const html = fs.readFileSync(DOCS + '/index.html', 'utf8');
const src = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));
const dummy = new Proxy(function () {}, { get: (t, k) => k === Symbol.toPrimitive ? () => '' : k === 'length' ? 0 : dummy, apply: () => dummy, construct: () => dummy, set: () => true });
const store = {};
const ctx = { console, Math, Date, JSON, Intl, Promise, Set, Map, Proxy, Number, String, Object, Array, RegExp, Symbol, Error, encodeURIComponent, decodeURIComponent, isNaN, parseFloat, parseInt, Infinity, NaN,
  document: dummy, navigator: { userAgent: 'node' }, location: { hash: '', pathname: '/', search: '' }, history: { state: null, replaceState() {}, pushState() {} },
  localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
  matchMedia: () => ({ matches: false, addEventListener() {} }), addEventListener() {}, removeEventListener() {}, scrollTo() {}, requestAnimationFrame() {}, setTimeout, clearTimeout, confirm: () => false, fetch: () => new Promise(() => {}) };
ctx.window = ctx; ctx.globalThis = ctx; vm.createContext(ctx);
vm.runInContext(src + `\n;globalThis.__E = { eligibility, spJudge, spTypesFor, myScore, mcScore, grade, funding, cpExplain, fromApi, DEFAULT_PROFILE, statusOf, syncHome, syncV2, rentalJudge, rStatus, rIsYouth, setListings: r => { LISTINGS = r; }, setConfig: c => { CONFIG = Object.assign(CONFIG, c); } };`, ctx, { filename: 'index.html' });
const E = ctx.__E;
E.setConfig(JSON.parse(fs.readFileSync(DOCS + '/config.json', 'utf8')));
const LS = JSON.parse(fs.readFileSync(DOCS + '/listings.json', 'utf8')).map(E.fromApi); E.setListings(LS);
let upd = ''; for (const f of ['data-updated.txt', 'updated.txt']) { try { upd = fs.readFileSync(DOCS + '/' + f, 'utf8').trim(); if (upd) break; } catch (e) {} }
const p = E.syncV2(E.syncHome(Object.assign({}, E.DEFAULT_PROFILE, JSON.parse(PJSON)))); p._set = Object.keys(JSON.parse(PJSON));   // 질문에 적힌 칸만 '입력함' — 예치금 0원이라고 말했으면 0원, 말하지 않았으면 모름 (2026-10-06)
if (opt.rental) {   // LH 임대: 입력하지 않은 칸은 '모름'(기본값 0·false 를 입력으로 보지 않음) — 조건 JSON 에 적은 칸만 입력한 것으로 표시
  const given = JSON.parse(PJSON), q = Object.assign({}, E.DEFAULT_PROFILE, given); q._set = Object.keys(given);
  const R = JSON.parse(fs.readFileSync(DOCS + '/lh-rental.json', 'utf8'));
  let ns = (R.notices || []).filter(N => opt.all || E.rStatus(N) !== '마감');
  if (opt.youth) ns = ns.filter(E.rIsYouth);
  if (opt.sido) ns = ns.filter(N => (N.region || '').startsWith(opt.sido));
  if (opt.name) ns = ns.filter(N => (N.name || '').includes(opt.name));
  const rout = ns.map(N => { const J = E.rentalJudge(N, q);
    return { id: N.id, link: 'https://cheongyakpass.kr/#/rdetail/' + encodeURIComponent(N.id), name: N.name, type: N.type, region: N.region, status: E.rStatus(N), posted: N.posted,
      schedule: N.schedule, office: N.office, url: N.url_mobile || N.url, pdf: N.notice_pdf, verdict: J.s,
      groups: J.groups.map(g => ({ group: g.name, s: g.s, items: g.items.map(i => i.s + (i.why ? '(' + i.why + ')' : '') + ': ' + i.t) })),
      rents: (N.rents || []).slice(0, 12) }; });
  console.log(JSON.stringify({ dataUpdated: R.updated, count: rout.length, statusWords: { ok: '신청 가능해 보여요', check: '확인 필요', no: '조건 밖', na: '해당 계층 없음', partial: '일부 계층 판정 못 함', unknown: '공고문 확인', unsupported: '판정 미지원 유형' }, results: rout }, null, 1));
  process.exit(0);
}
let list = LS;
if (opt.ids) { const ids = String(opt.ids).split(','); list = LS.filter(L => ids.includes(L.id)); }
else { if (!opt.all) list = list.filter(L => E.statusOf(L) !== '마감'); if (opt.sido) list = list.filter(L => L.sido === opt.sido); if (opt.name) list = list.filter(L => (L.name + ' ' + (L.address || '')).includes(opt.name)); }
const r2 = v => v == null ? null : Math.round(v * 100) / 100;
const out = list.map(L => {
  const x = E.cpExplain(L.id, p), g = E.grade(L), s = E.myScore(L, p), f = E.funding(L, p, { family: 0 });
  return { id: L.id, link: 'https://cheongyakpass.kr/#/detail/' + encodeURIComponent(L.id), name: L.name, unit: L.unit, sido: L.sido, district: L.district, kind: L.kind, dtl: L.houseDtl, status: E.statusOf(L),
    dates: { notice: L.notice, special: L.specialApply, apply: L.apply, applyEnd: L.applyEnd, winner: L.winner }, price: L.price, regulated: L.regulated,
    verdict: x.verdict, reason: x.reason, notOk: x.items.filter(i => i.s === 'fail' || i.s === 'warn').map(i => ({ k: i.k, s: i.s, v: i.v, cause: i.cause, note: i.note })),
    special: x.special.map(r => ({ type: r.type, v: r.v, stage: r.stage, fail: r.fail, warn: r.warn })),
    score: s.total, scoreMiss: s.miss, grade: { g: g.g, lo: r2(g.lo), hi: r2(g.hi), cost: r2(g.cost), mktLow: L.mktLow, mktBase: L.mktBase, mktNote: L.mktNote },
    funding: L.mktBase == null ? '시세 없음 - 자금 계산 생략(엔진 오류 의심 구간)' : { gapLive: r2(f.gapLive), loan: r2(f.loan), limitBy: f.limitBy, gapJeonse: r2(f.gapJeonse) },
    checks: L.checks, pdf: L.noticePdf, applyhome: L.sources && L.sources[0] && L.sources[0][1] };
});
console.log(JSON.stringify({ dataUpdated: upd, count: out.length, results: out }, null, 1));
