// 브라우저가 챗봇 서버로 보낼 '엔진 결과'를 Node 에서 똑같이 만든다 (시험·평가용).
// 청약패스 docs/index.html 의 판정 함수를 그대로 실행한다. 저장소 파일은 읽기만 한다.
const fs = require('fs'), vm = require('vm');

function loadEngine(DOCS, listingsPath) {
  const html = fs.readFileSync(DOCS + '/index.html', 'utf8');
  const src = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));
  const dummy = new Proxy(function () {}, { get: (t, k) => k === Symbol.toPrimitive ? () => '' : k === 'length' ? 0 : dummy, apply: () => dummy, construct: () => dummy, set: () => true });
  const store = {};
  const ctx = { console, Math, Date, JSON, Intl, Promise, Set, Map, Proxy, Number, String, Object, Array, RegExp, Symbol, Error, encodeURIComponent, decodeURIComponent, isNaN, parseFloat, parseInt, Infinity, NaN,
    document: dummy, navigator: { userAgent: 'node' }, location: { hash: '', pathname: '/', search: '' }, history: { state: null, replaceState() {}, pushState() {} },
    localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
    matchMedia: () => ({ matches: false, addEventListener() {} }), addEventListener() {}, removeEventListener() {}, scrollTo() {}, requestAnimationFrame() {}, setTimeout, clearTimeout, confirm: () => false, fetch: () => new Promise(() => {}) };
  ctx.window = ctx; ctx.globalThis = ctx; vm.createContext(ctx);
  vm.runInContext(src + `\n;globalThis.__E = { cpExplain, itemBasis, myScore, grade, fromApi, DEFAULT_PROFILE, statusOf, syncHome, syncV2, setListings: r => { LISTINGS = r; }, setConfig: c => { CONFIG = Object.assign(CONFIG, c); } };`, ctx, { filename: 'index.html' });
  const E = ctx.__E;
  E.setConfig(JSON.parse(fs.readFileSync(DOCS + '/config.json', 'utf8')));
  const LS = JSON.parse(fs.readFileSync(listingsPath || DOCS + '/listings.json', 'utf8')).map(E.fromApi);
  E.setListings(LS);
  let updated = '';
  try { updated = fs.readFileSync(DOCS + '/data-updated.txt', 'utf8').trim(); } catch (e) {}
  return { E, LS, updated };
}

// 브라우저에서도 이 함수와 같은 모양으로 만들면 된다 (index.html 쪽 구현 참고용).
function buildEngine(eng, listingId, profileIn) {
  const { E, LS, updated } = eng;
  const L = LS.find(x => x.id === listingId);
  if (!L) throw new Error('공고 없음: ' + listingId);
  const p = E.syncV2(E.syncHome(Object.assign({}, E.DEFAULT_PROFILE, profileIn || {})));
  const x = E.cpExplain(L.id, p), s = E.myScore(L, p), g = E.grade(L);
  const r2 = v => v == null ? null : Math.round(v * 100) / 100;
  return {
    data_updated: updated,
    listing: { id: L.id, name: L.name, unit: L.unit, sido: L.sido, district: L.district, kind: L.kind, dtl: L.houseDtl || null, status: E.statusOf(L),
      price: L.price, regulated: !!L.regulated, dates: { notice: L.notice, special: L.specialApply, apply: L.apply, applyEnd: L.applyEnd, winner: L.winner },
      link: 'https://cheongyakpass.kr/#/detail/' + encodeURIComponent(L.id), pdf: L.noticePdf || null },
    verdict: x.verdict, reason: x.reason || '',
    items: x.items.map(i => { const b = E.itemBasis(L, i.k) || {}; return { k: i.k, s: i.s, v: i.v == null ? '' : String(i.v), cause: i.cause || null, note: i.note || '', basis: b.kind || null }; }),
    special: (x.special || []).map(r => ({ type: r.type, v: r.v, stage: r.stage || null, fail: r.fail || [], warn: r.warn || [] })),
    score: { total: s.total, parts: (s.parts || []).map(x => x.v), miss: s.miss || [] },
    grade: { lo: r2(g.lo), hi: r2(g.hi) },
  };
}

module.exports = { loadEngine, buildEngine };

if (require.main === module) {
  const [DOCS, id, pj] = process.argv.slice(2);
  const eng = loadEngine(DOCS);
  console.log(JSON.stringify(buildEngine(eng, id, JSON.parse(pj || '{}')), null, 1));
}
