// 청약패스 화면(docs/index.html)의 판정·계산 함수를 Node 에서 그대로 불러 쓴다 (청약봇 V2).
// 판정 규칙을 이 폴더에 다시 적지 않는다 — 화면과 청약봇 결론이 갈라지지 않게 (tools/qa/past_chat.cjs B3 와 같은 원칙).
// 저장소 파일은 읽기만 한다. today 를 주면 화면의 TODAY(한국 날짜)를 그 날로 고정한다(시험용).
const fs = require('fs'), vm = require('vm'), path = require('path');

const EXPORTS = ['fromApi', 'eligBucket', 'eligibility', 'spJudge', 'spTypesFor', 'SP_NAME', 'ELIG_NAME', 'myScore', 'grade', 'GNAME', 'marginText', 'funding',
  'statusOf', 'judgeScope', 'genNone', 'isRental', 'isNewlywedTown', 'kindOf', 'regionScore', 'chatEnginePayload', 'DEFAULT_PROFILE', 'syncHome', 'syncV2', 'fmt'];

function fixedDate(today) {
  if (!today) return Date;
  const t = new Date(today + 'T03:00:00Z').getTime();   // 한국 12시
  class D extends Date { constructor(...a) { if (a.length) super(...a); else super(t); } static now() { return t; } }
  return D;
}

function loadEngine({ docs = path.join(__dirname, '../../docs'), listings = null, config = null, today = null } = {}) {
  const html = fs.readFileSync(path.join(docs, 'index.html'), 'utf8');
  const src = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));
  const dummy = new Proxy(function () {}, { get: (t, k) => k === Symbol.toPrimitive ? () => '' : k === 'length' ? 0 : dummy, apply: () => dummy, construct: () => dummy, set: () => true });
  const store = {};
  const ctx = { console, Math, Date: fixedDate(today), JSON, Intl, Promise, Set, Map, WeakMap, Proxy, Number, String, Object, Array, RegExp, Symbol, Error, encodeURIComponent, decodeURIComponent, isNaN, isFinite, parseFloat, parseInt, Infinity, NaN,
    document: dummy, navigator: { userAgent: 'node' }, location: { hash: '', pathname: '/', search: '' }, history: { state: null, replaceState() {}, pushState() {} },
    localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
    matchMedia: () => ({ matches: false, addEventListener() {} }), addEventListener() {}, removeEventListener() {}, scrollTo() {}, requestAnimationFrame() {}, setTimeout, clearTimeout, confirm: () => false, fetch: () => new Promise(() => {}) };
  ctx.window = ctx; ctx.globalThis = ctx; vm.createContext(ctx);
  vm.runInContext(src + `\n;globalThis.__E = { ${EXPORTS.join(', ')}, TODAY, setListings: r => { LISTINGS = r; }, setConfig: c => { CONFIG = Object.assign(CONFIG, c); }, on };`, ctx, { filename: 'index.html' });
  const E = ctx.__E;
  E.setConfig(config || JSON.parse(fs.readFileSync(path.join(docs, 'config.json'), 'utf8')));
  const raw = listings || JSON.parse(fs.readFileSync(path.join(docs, 'listings.json'), 'utf8'));
  const rows = Array.isArray(raw) ? raw : raw.items;
  const LS = rows.filter(x => !x.sample).map(E.fromApi);
  E.setListings(LS);
  /* 받은 조건에 적힌 칸 = 사용자가 넣은 칸(_set) — 빈칸은 '모름'으로 보는 판정(2026-10-06 v1.58.3)에서 배우자 집 '없음' 등을 빈칸으로 보지 않게 (2026-10-07) */
  const profileOf = p => (p ? E.syncV2(E.syncHome(Object.assign({}, E.DEFAULT_PROFILE, p, Array.isArray(p._set) ? {} : { _set: Object.keys(p) }))) : null);
  return { E, LS, raw: rows, today: E.TODAY, profileOf };
}

module.exports = { loadEngine };
