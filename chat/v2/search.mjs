// 실제 데이터 검색 → 후보 → 조건 걸러내기 → (내 자격) → 추천 점수·관점별 1등 → 결과 없을 때 완화안.
// 판정은 engine.cjs 가 부른 청약패스 화면 함수(eligBucket·spJudge·grade·statusOf·myScore) 결과만 쓴다. 여기서 자격을 새로 계산하지 않는다.
// 값마다 상태를 붙인다: 확인(청약홈·모집공고문·판정 엔진) / 추정(시세·직선거리) / 확인 불가(데이터 없음) — 지어내지 않는다.
import { DISTRICTS, AREAS, SP_LABEL, distKm } from './lexicon.mjs';

// 받침에 맞는 조사 ('송파구가', '광명시가', '철산동이') — AI 심사 회차 3: '송파구이 아님' 어색
export const josa = (w, a, b) => { const c = String(w).replace(/[^가-힣]+$/, '').slice(-1); if (!c) return w + a; const code = c.charCodeAt(0) - 0xac00; return w + (code >= 0 && code % 28 ? a : b); };
const ELIG_RANK = { ok: 3, unsure: 2, r2: 1, no: 0 };
const ELIG_WORD = { ok: '신청 가능', unsure: '확인 필요', r2: '2순위만', no: '신청 불가' };
const GRADE_RANK = { lotto: 4, consider: 3, flat: 2, pass: 1, unknown: 0 };
export const SITE = 'https://cheongyakpass.kr';

// ---- 데이터 묶음 ----
// D = { E: 화면 판정 함수들, rows: [{L, raw, past, noJudge}], today, profileOf }. Node 에서는 node-data.mjs 의 loadData, 브라우저(청약패스 화면)에서는 browser.mjs 의 fromScreen 이 만든다.
// ---- 한 주택형의 사실(값 + 상태 + 출처) ----
export function factsOf(D, row) {
  const { L, raw } = row, E = D.E;
  const st = row.past ? '마감(과거 공고)' : E.statusOf(L) || '일정 확인';
  const g = E.grade(L);
  const near = kind => { const n = (raw.nearby || []).filter(x => x.kind === kind).sort((a, b) => a.m - b.m)[0];
    if (!n) return { state: '확인 불가', why: raw.geo ? '가까운 ' + kind + ' 정보 없음' : '단지 좌표 없음' };
    if (!raw.geo || raw.geo.precision !== 'exact') return { state: '확인 불가', name: n.name, why: '단지 좌표가 동 단위라 거리를 재지 않음' };
    return { state: '추정', name: n.name, m: n.m, walk: n.walk, src: '직선거리로 잰 도보 추정 (OpenStreetMap 위치)' }; };
  const cx = raw.complex || null;
  const comp = (raw.competition && raw.competition.rows || []).filter(r => r.rate_num != null);
  return {
    id: L.id, nid: L.id.split('-')[0], name: L.name, unit: String(L.unitName || L.unit || '').trim(), sido: L.sido, district: L.district || '', address: raw.address || L.address || '',
    past: row.past, status: st, kind: E.kindOf(L) || '', category: L.category, houseDtl: L.houseDtl, rental: !!L.rental, town: E.isNewlywedTown(L),
    price: { v: L.price, state: '확인', src: '청약홈 공고 (주택형 최고 분양가)', label: L.rental ? '임대보증금' : '분양가' },
    area: { v: L.area, state: '확인', src: '청약홈 공고 (전용면적)' },
    units: { general: L.households || 0, special: (L.specialUnits && L.specialUnits.total) || 0, state: '확인', src: '청약홈 공고' },
    complex: cx && cx.status === '확인' ? { households: cx.households, buildings: cx.buildings, single: cx.single, state: '확인', src: '모집공고문 공급규모' } : { single: (cx && cx.single) || 'unknown', state: '확인 불가', why: '모집공고문에서 단지 규모 문장을 못 읽음' },
    rooms: { state: '확인 불가', why: '방·욕실 수는 아직 모으지 않음 (STEP 0-4)' },
    station: near('역'), school: near('초등학교'),
    margin: g.g === 'unknown' ? { g: 'unknown', state: '확인 불가', why: '주변 시세 거래가 모자람' } : { g: g.g, lo: g.lo, hi: g.hi, name: E.GNAME[g.g], state: '추정', src: L.mktNote || '국토부 실거래 기준 이 서비스 추정', count: L.mktCount || 0 },
    jeonse: L.jeonse ? { v: L.jeonse, state: '추정', src: L.jeonseNote || '국토부 전세 실거래 기준 추정' } : { state: '확인 불가' },
    competition: comp.length ? { rows: comp.map(r => ({ rank: r.rank, reside: r.reside, rate: r.rate_num })), state: '확인', src: '청약홈 경쟁률' } : null,
    dates: { notice: L.notice, special: L.specialApply, apply: L.apply, applyEnd: L.applyEnd, winner: L.winner },
    geo: raw.geo && raw.geo.lat ? { lat: raw.geo.lat, lng: raw.geo.lng, precise: raw.geo.precision === 'exact' } : null,
    // 보유 계획(5년 후 갈아타기·장기보유)에 걸리는 제한 — 모집공고문에서 읽은 값 (샘플 5). 전매제한은 아직 모으지 않아 '공고문 확인'
    limits: { duty: L.residenceDuty == null ? null : +L.residenceDuty, rewin: (() => { const x = (L.limits || []).find(l => l[0] === '재당첨 제한'); return x ? (x[1] === '없음' ? 0 : parseInt(x[1], 10) || null) : null; })(), priceCap: L.priceCap == null ? null : !!L.priceCap, src: '모집공고문' },
    link: SITE + '/#/detail/' + encodeURIComponent(L.id), pdf: L.noticePdf || null,
  };
}

// ---- 조건 하나 평가: pass / fail / unknown ----
const norm = s => String(s || '').replace(/\s+/g, '');
function inRegion(f, r) {
  if (r.sido && f.sido !== r.sido) return false;
  if (r.district) { const d = norm(f.district); if (d.includes(norm(r.district))) return true; if (r.words && r.words.some(w => norm(f.address).includes(w))) return true; return false; }
  if (r.words && r.words.length) return r.words.some(w => norm(f.address).includes(w) || norm(f.name).includes(w)) || (!r.sido ? false : !r.district && !r.words.length);
  return true;
}
export function evalCond(D, row, f, c, ctx) {
  const v = c.value;
  switch (c.key) {
    case 'region_in': return v.some(r => inRegion(f, r)) ? ['pass'] : ['fail', josa(v.map(r => r.label).join('·'), '이', '가') + ' 아닌 곳'];
    case 'region_out': return v.some(r => inRegion(f, r)) ? ['fail', v.map(r => r.label).join('·') + ' 제외'] : ['pass'];
    case 'price_max': return f.price.v == null ? ['unknown', '분양가 없음'] : f.price.v <= v + 1e-9 ? ['pass'] : ['fail', '예산 초과(' + v + '억)'];
    case 'price_min': return f.price.v == null ? ['unknown'] : f.price.v >= v ? ['pass'] : ['fail', v + '억 미만'];
    case 'price_range': return f.price.v == null ? ['unknown'] : f.price.v >= v[0] && f.price.v < v[1] ? ['pass'] : ['fail', '가격대가 ' + v[0] + '억대가 아님'];
    case 'area': return f.area.v == null ? ['unknown'] : f.area.v >= v.min && f.area.v <= v.max ? ['pass'] : ['fail', '면적이 ' + v.label.replace(/\(.*\)/, '') + ' 밖'];
    case 'households_min': return f.complex.state !== '확인' ? ['unknown', '단지 규모 확인 필요'] : f.complex.households >= v ? ['pass'] : ['fail', '단지 ' + v + '세대 미만'];
    case 'not_single': return f.complex.single === 'no' ? ['pass'] : f.complex.single === 'maybe' ? ['fail', '나홀로일 가능성'] : ['unknown', '단지 규모 확인 필요'];
    case 'rooms': return ['unknown', '방·욕실 구조 확인 필요'];
    case 'station_walk': return f.station.state !== '추정' ? ['unknown', '역 거리 확인 불가'] : f.station.walk <= v ? ['pass'] : ['fail', '역 도보 ' + v + '분 넘음'];
    case 'school_walk': return f.school.state !== '추정' ? ['unknown', '학교 거리 확인 불가'] : f.school.walk <= v.min ? ['pass'] : ['fail', '초등학교 도보 ' + v.min + '분 넘음'];
    case 'commute': return ['unknown', v.place + ' 출퇴근 시간 확인 불가'];
    case 'supply': {
      if (v.startsWith('sp:')) { const t = v.slice(3), types = D.E.spTypesFor(row.L); if (!types.includes(t)) return ['fail', SP_LABEL[t] + ' 특별공급 없음']; const n = row.L.specialUnits && row.L.specialUnits[t]; return n === 0 && !f.town ? ['fail', SP_LABEL[t] + ' 특별공급 0세대'] : ['pass']; }
      if (v === 'remainder') return f.category === 'remainder' ? ['pass'] : ['fail', '무순위 아님'];
      if (v === 'town') return f.town ? ['pass'] : ['fail', '신혼희망타운 아님'];
      if (v === 'public') return f.houseDtl === '국민' ? ['pass'] : ['fail', '공공분양 아님'];
      if (v === 'private') return f.houseDtl === '민영' ? ['pass'] : ['fail', '민영 아님'];
      if (v === 'rental') return f.rental ? ['pass'] : ['fail', '공공임대 아님'];
      return ['unknown'];
    }
    case 'status': return v.includes(f.status) ? ['pass'] : ['fail', v.join('·') + ' 아님'];
    case 'eligible_only': { if (row.noJudge) return ['unknown', '지난 공고 개요만 있어 그때 자격은 판정하지 않음']; if (!ctx.profile) return ['unknown', '내 조건을 넣지 않아 자격 판정 전']; const b = ctx.elig(row); return b === 'ok' ? ['pass'] : b === 'unsure' ? ['unknown', '자격 확인 필요'] : ['fail', '내 자격으로 ' + ELIG_WORD[b]]; }
    case 'margin': return f.margin.g === 'unknown' ? ['unknown', '시세 확인 불가'] : GRADE_RANK[f.margin.g] >= GRADE_RANK.consider ? ['pass'] : ['fail', '시세 차익 작음(추정)'];
    case 'new_build': return ['pass'];
    case 'line': {   // 노선 역세권: 단지 좌표에서 그 노선 역 중 가장 가까운 역까지 직선거리 (역 좌표: OpenStreetMap)
      const st = D.lines && D.lines.lines && D.lines.lines[v.line];
      if (!st || !st.length) return ['unknown', v.line + ' 역 정보 없음'];
      if (!f.geo) return ['unknown', '단지 좌표 없음'];
      const near = nearestOn(st, f.geo); f.line = f.line || {}; f.line[v.line] = near;
      return near.m <= v.m ? ['pass'] : ['fail', v.line + ' 역에서 ' + (v.m / 1000) + 'km 넘음'];   // 거리는 카드 노선 줄에 (빠진 이유를 거리마다 따로 세지 않게)
    }
    default: return ['unknown'];
  }
}

export function nearestOn(stations, geo) {
  let best = null;
  for (const x of stations) { const m = Math.round(distKm(geo, x) * 1000); if (!best || m < best.m) best = { name: x.name, m }; }
  return best;
}

// ---- 검색 한 번 ----
// 여러 절에서 나온 지역(포함)은 '또는'으로 합친다 ('광명 철산동, 구로 개봉동이나 고척동')
export function mergeRegions(C) {
  const out = [], seen = {};
  for (const c of C.conds) {
    if (c.key !== 'region_in') { out.push(c); continue; }
    const k = c.weight + (c.explore_ok ? '+' : '');
    if (seen[k]) { seen[k].value = seen[k].value.concat(c.value.filter(v => !seen[k].value.some(w => w.label === v.label))); seen[k].text += '·' + c.text; }
    else { seen[k] = { ...c, value: c.value.slice() }; out.push(seen[k]); }
  }
  return { ...C, conds: out };
}

export function search(D, C0, { profile = null, limit = 3, inner = false } = {}) {   // 카드는 3곳까지 (AI 심사 회차 1: 5곳은 정보 과다 — 나머지는 한 줄 목록)
  const C = mergeRegions(C0);
  const p = profile ? D.profileOf(Object.assign({}, profile, assumeToProfile(C.assume || {}))) : null;   // 저장된 내 조건이 없으면 판정하지 않는다 — 질문 속 가정(신혼부부 등)만으로는 자격을 단정할 수 없음
  const eligCache = new Map();
  const ctx = { profile: p, elig: row => { if (!eligCache.has(row.L.id)) eligCache.set(row.L.id, D.E.eligBucket(row.L, p)); return eligCache.get(row.L.id); } };
  const hasStatus = C.conds.some(c => c.key === 'status');
  const pool = D.rows.filter(r => C.scope && C.scope.past ? true : !r.past);
  const facts = new Map(pool.map(r => [r.L.id, factsOf(D, r)]));
  const live = pool.filter(r => r.past || hasStatus || ['접수 중', '접수 예정'].includes(facts.get(r.L.id).status));
  const req = C.conds.filter(c => c.weight === 'required'), pref = C.conds.filter(c => c.weight !== 'required');
  const out = { total: live.length, excluded: {}, ok: [], unsure: [], refused: [] };
  const near = [];   // 필수 조건 몇 개만 어긋난 곳 — 결과가 없을 때 '조건에 가장 가까운 곳'
  for (const r of live) {
    const f = facts.get(r.L.id), res = req.map(c => [c, ...evalCond(D, r, f, c, ctx)]);
    const fail = res.find(x => x[1] === 'fail');
    if (fail) { out.excluded[fail[2] || fail[0].key] = (out.excluded[fail[2] || fail[0].key] || 0) + 1;
      near.push({ row: r, f, misses: res.filter(x => x[1] === 'fail').map(x => x[2] || x[0].key), unknown: res.filter(x => x[1] === 'unknown').map(x => x[2] || x[0].key) }); continue; }
    const unk = res.filter(x => x[1] === 'unknown');
    const prefRes = pref.map(c => [c, ...evalCond(D, r, f, c, ctx)]);
    const item = { row: r, f, unknown: unk.map(x => x[2] || x[0].key), pref: prefRes.map(([c, s, why]) => ({ key: c.key, text: c.text, s, why })), score: 0 };
    item.genNone = D.E.genNone(r.L);
    if (p && !r.noJudge) { item.elig = ctx.elig(r); item.sp = D.E.spTypesFor(r.L).map(t => ({ type: t, label: SP_LABEL[t] || t, s: D.E.spJudge(r.L, p, t).s })); }
    item.score = prefScore(item, C);
    (unk.length ? out.unsure : out.ok).push(item);
  }
  const order = (a, b) => (b.elig != null ? ELIG_RANK[b.elig] : 0) - (a.elig != null ? ELIG_RANK[a.elig] : 0) || b.score - a.score || (a.f.price.v || 99) - (b.f.price.v || 99);
  out.ok.sort(order); out.unsure.sort(order);
  if (p) { out.refused = out.ok.filter(x => x.elig === 'no'); out.ok = out.ok.filter(x => x.elig !== 'no'); }   // 불가는 추천이 아니라 '참고'
  out.groups = groupByNotice(out.ok);
  out.perspectives = perspectives(out.ok, C);
  if (inner) return out;
  out.relax = out.ok.length ? [] : relaxOptions(D, C, profile);
  if (!out.ok.length && !out.unsure.length) {   // 하나씩 늦춰도 안 생기면: 어긋난 조건이 가장 적은 곳 (공고당 1개, 거리 가까운 순) — '없어요'로 끝내지 않는다
    const m = Math.min(...near.map(x => x.misses.length));
    const cand = near.filter(x => x.misses.length === m && !x.row.past);
    const regs = C.conds.filter(c => c.key === 'region_in').flatMap(c => c.value).filter(v => v.lat);
    const d = x => regs.length && x.f.geo ? Math.min(...regs.map(v => distKm(x.f.geo, v))) : 999;
    const er = x => ctx.profile && !x.row.noJudge ? ELIG_RANK[ctx.elig(x.row)] || 0 : 0;   // 신청할 수 있는 곳을 먼저 (샘플 3 점검: 신청 불가 곳이 맨 위)
    const seen = new Set(); out.closest = cand.sort((a, b) => er(b) - er(a) || d(a) - d(b) || (a.f.price.v || 99) - (b.f.price.v || 99)).filter(x => !seen.has(x.f.nid) && seen.add(x.f.nid)).slice(0, 3)
      .map(x => ({ ...x, km: d(x) < 999 ? Math.round(d(x)) : null, elig: ctx.profile && !x.row.noJudge ? ctx.elig(x.row) : undefined, genNone: D.E.genNone(x.row.L) }));
  }
  // 예산을 조금(10%) 넘는 곳 — '관심 단지로만' 보여 준다 (사용자 예시: 예산을 다소 넘어 관심 단지로만 체크)
  const pm = C.conds.find(c => c.key === 'price_max' && c.weight === 'required');
  if (out.ok.length && pm) { const C2 = JSON.parse(JSON.stringify(C)); C2.conds.find(c => c.key === 'price_max').value = Math.round(pm.value * 1.1 * 100) / 100;
    const have = new Set(out.ok.map(x => x.f.nid)); out.nearMiss = groupByNotice(search(D, C2, { profile, inner: true }).ok.filter(x => !have.has(x.f.nid))).slice(0, 2); }
  out.explore = exploreNearby(D, C, live, facts);
  // 노선 조건이면: 그 노선 역세권 공고가 지금 몇 곳이고 가장 싼 곳이 얼마인지 — '판교·분당권은 예산 안에 닿지 않아요' 같은 판단의 근거 (샘플 4)
  out.lineInfo = C.conds.filter(c => c.key === 'line').map(c => {
    const st = D.lines && D.lines.lines && D.lines.lines[c.value.line]; if (!st) return { line: c.value.line, missing: true };
    const near = live.filter(r => !r.past).map(r => ({ r, f: facts.get(r.L.id) })).filter(x => x.f.geo).map(x => ({ ...x, st: nearestOn(st, x.f.geo) })).filter(x => x.st.m <= c.value.m);
    const nids = new Set(near.map(x => x.f.nid)), prices = near.map(x => x.f.price.v).filter(v => v != null);
    return { line: c.value.line, m: c.value.m, notices: nids.size, types: near.length, minPrice: prices.length ? Math.min(...prices) : null, stations: [...new Set(near.map(x => x.st.name))] };
  });
  // '마포구 말고도 같은 조건으로' (scope.expand): 지역만 풀고 나머지 조건은 그대로 — 그 지역 밖 후보를 따로 (2026-10-04 사용자 샘플 3)
  const regC = C.conds.filter(c => c.key === 'region_in' && c.weight === 'required');
  if (C.scope && C.scope.expand && regC.length) {
    const C3 = JSON.parse(JSON.stringify(C)); C3.conds = C3.conds.filter(c => c.key !== 'region_in'); C3.scope = { ...C3.scope, expand: false };
    const r3 = search(D, C3, { profile, inner: true });
    const regs = regC.flatMap(c => c.value), inside = x => regs.some(v => inRegion(x.f, v));
    const pts = regs.filter(v => v.lat), dist = x => pts.length && x.f.geo ? Math.min(...pts.map(v => distKm(x.f.geo, v))) : 999;
    const pool3 = (r3.ok.length ? r3.ok : r3.unsure).filter(x => !inside(x));
    pool3.forEach(x => { x.km = dist(x) < 999 ? Math.round(dist(x)) : null; x.rank3 = x.score - (dist(x) < 999 ? Math.min(6, dist(x) / 8) : 4); });   // 그 지역에서 멀수록 조금 뒤로 (생활권)
    const near30 = x => x.km != null && x.km <= 30 ? 1 : 0;   // 생활권(직선 30km) 안을 먼저 — 샘플 3 점검: 50km 떨어진 곳이 30km 곳보다 앞
    pool3.sort((a, b) => near30(b) - near30(a) || (b.elig != null ? ELIG_RANK[b.elig] : 0) - (a.elig != null ? ELIG_RANK[a.elig] : 0) || b.rank3 - a.rank3 || (a.f.price.v || 99) - (b.f.price.v || 99));
    out.outside = { base: [...new Set(regs.map(v => v.label))], groups: groupByNotice(pool3).slice(0, limit), total: new Set(pool3.map(x => x.f.nid)).size, unsure: !r3.ok.length };
  }
  out.profile = !!p; out.limit = limit;
  return out;
}

// 이번 질문의 가정(신혼부부·현금 5억)을 판정 엔진 입력 이름으로 — 저장된 내 조건은 바꾸지 않는다
function assumeToProfile(a) {
  const p = {};
  if (a.married) { p.married = true; p.marriedOn = p.marriedOn || null; }
  if (a.cash != null) p.cash = Math.round(a.cash * 10000);
  if (a.income != null) p.income = a.income;
  if (a.homeless === true) { p.selfOwn = false; p.spouseOwn = false; p.hhHomes = '0'; }
  if (a.homeless === false) { p.selfOwn = true; p.hhHomes = '1'; }
  if (a.kids != null) { p.kidsMinor = a.kids; }
  return p;
}

function prefScore(item, C) {
  let s = 0;
  for (const x of item.pref) {
    const w = x.key === 'region_in' ? 4 : x.key === 'margin' ? 2 : x.key === 'commute' ? 0 : 3;   // 질문에 적은 선호(초품아·역세권)는 시세 차익보다 앞 (AI 심사 회차 1: '초품아 위주'인데 조건 안 맞는 곳이 위에)
    s += x.s === 'pass' ? w : x.s === 'fail' ? -w : 0;
  }
  const g = item.f.margin.g; s += { lotto: 1.5, consider: 1, flat: 0, pass: -0.5, unknown: 0 }[g] || 0;
  const cm = C.conds.filter(c => c.key === 'commute');   // 출퇴근지까지 직선거리(참고) — 시간 아님. 여럿이면 평균. 출퇴근이 주된 조건이면 거리가 순서를 정한다
  if (cm.length) { const ds = item.f.geo ? cm.map(c => distKm(item.f.geo, c.value)) : null; const avgKm = ds ? ds.reduce((a, b) => a + b, 0) / ds.length : null; s -= avgKm == null ? 6 : Math.min(12, avgKm / 4) + (avgKm > 40 ? 6 : 0); item.far = avgKm != null && avgKm > 40; }   // 직장에서 40km 넘으면 뒤로 (회차 1: 판교 출퇴근인데 세종·인천이 위에)
  if (item.f.dates.applyEnd) s += 0.01;
  return Math.round(s * 100) / 100;
}

function groupByNotice(items) {
  const g = new Map();
  for (const it of items) { const k = it.f.nid; if (!g.has(k)) g.set(k, []); g.get(k).push(it); }
  return [...g.values()].map(a => ({ nid: a[0].f.nid, name: a[0].f.name, best: a[0], types: a }));
}

function perspectives(items, C) {
  if (!items.length) return [];
  const by = (label, fn, why) => { const x = items.slice().sort(fn)[0]; return x ? { label, id: x.f.id, name: x.f.name, unit: x.f.unit, why: why(x) } : null; };
  const out = [
    by('가격 우선', (a, b) => (a.f.price.v || 99) - (b.f.price.v || 99), x => '분양가 ' + fmtEok(x.f.price.v)),
    by('시세 차익 우선(추정)', (a, b) => (GRADE_RANK[b.f.margin.g] - GRADE_RANK[a.f.margin.g]) || ((b.f.margin.lo || -99) - (a.f.margin.lo || -99)), x => x.f.margin.g === 'unknown' ? '시세 확인 불가' : '마진 ' + signed(x.f.margin.lo) + '~' + signed(x.f.margin.hi) + ' 추정'),
  ];
  if (items.some(x => x.elig)) out.unshift(by('당첨 길 우선', (a, b) => (ELIG_RANK[b.elig] - ELIG_RANK[a.elig]) || ((b.sp || []).filter(s => s.s === 'ok').length - (a.sp || []).filter(s => s.s === 'ok').length), x => (x.f.town ? '신혼희망타운' : x.f.category === 'remainder' ? '무순위' : x.genNone ? '특별공급 기준' : '일반공급') + ' ' + ELIG_WORD[x.elig] + ((x.sp || []).some(s => s.s === 'ok') ? ' · 특공 ' + x.sp.filter(s => s.s === 'ok').map(s => s.label).join('·') + ' 가능' : '')));
  for (const c of C.conds.filter(c => c.key === 'commute')) {
    const xs = items.filter(x => x.f.geo); if (!xs.length) continue;
    out.push(by(c.value.place + ' 가까운 순', (a, b) => (a.f.geo ? distKm(a.f.geo, c.value) : 999) - (b.f.geo ? distKm(b.f.geo, c.value) : 999), x => x.f.geo ? c.value.place + '까지 직선 약 ' + Math.round(distKm(x.f.geo, c.value)) + 'km (시간은 확인 불가)' : '좌표 없음'));
  }
  const seen = new Set(); return out.filter(Boolean).filter(x => { const k = x.label; if (seen.has(k)) return false; seen.add(k); return true; });
}

// 결과가 없을 때: 필수 조건을 하나씩 한 단계 늦췄을 때 생기는 후보 수 (0곳이면 버튼을 만들지 않음)
function relaxOptions(D, C, profile) {
  const opts = [];
  const tryC = (label, mut) => { const C2 = JSON.parse(JSON.stringify(C)); mut(C2); const r = search(D, C2, { profile, inner: true }); const all = r.ok.concat(r.unsure), n = new Set(all.map(x => x.f.nid)).size; if (n) opts.push({ label, count: n, conds: C2.conds, groups: groupByNotice(all).slice(0, 3) }); };   // 확인 필요 후보도 센다 (내 조건이 없어 자격만 모르는 곳 등)
  for (const c of C.conds.filter(c => c.weight === 'required')) {
    const i = C.conds.indexOf(c);
    if (c.key === 'price_max') tryC(c.value + '억 → ' + Math.round(c.value * 1.1 * 10) / 10 + '억', X => { X.conds[i].value = Math.round(c.value * 1.1 * 10) / 10; });
    else if (c.key === 'households_min') tryC(c.value + '세대 → ' + Math.round(c.value * 0.7) + '세대', X => { X.conds[i].value = Math.round(c.value * 0.7); });
    else if (c.key === 'region_in') tryC(c.value.map(r => r.label).join('·') + ' → 인접 지역 포함', X => { X.conds[i].value = widen(c.value); });
    else if (c.key === 'area') tryC(c.value.label + ' → 면적 조건 넓히기', X => { X.conds[i].value = { min: c.value.min - 15, max: c.value.max + 15, label: '전용 ' + Math.max(0, c.value.min - 15) + '~' + (c.value.max + 15) + '㎡' }; });
    else if (c.key === 'status') tryC('접수 중·예정 모두', X => { X.conds.splice(i, 1); });
    else if (c.key === 'line') tryC(c.value.line + ' 역까지 직선 ' + (c.value.m / 1000) + 'km → 3km', X => { X.conds[i].value = { ...c.value, m: 3000 }; });
    else if (['supply', 'eligible_only', 'not_single', 'rooms', 'region_out'].includes(c.key)) tryC((c.text || c.key) + ' 조건 빼기', X => { X.conds.splice(i, 1); });
  }
  if (!C.scope || !C.scope.past) tryC('최근 마감된 지난 공고 보기', X => { X.scope = { past: true }; X.conds.push({ key: 'status', value: ['마감(과거 공고)'], weight: 'required', text: '지난 공고' }); });
  return opts.slice(0, 6);
}

// 인접 지역: 좌표 거리로만 고른다 (AI 기억으로 지역을 만들지 않음)
export function widen(regs, km = 12) {
  const out = regs.slice();
  for (const r of regs) {
    const c = r.lat ? r : DISTRICTS.find(d => d[1] === r.district) ? { lat: DISTRICTS.find(d => d[1] === r.district)[2], lng: DISTRICTS.find(d => d[1] === r.district)[3] } : null;
    if (!c) continue;
    for (const [sd, dn, lat, lng] of DISTRICTS) { const d = distKm(c, { lat, lng }); if (d <= km && !out.some(o => o.district === dn)) out.push({ sido: sd, district: dn, label: dn, lat, lng, near_of: r.label, km: Math.round(d) }); }
  }
  return out;
}
function exploreNearby(D, C, live, facts) {
  const ex = C.conds.filter(c => c.key === 'region_in' && (c.weight === 'explore' || c.explore_ok));
  if (!ex.length) return null;
  const regs = ex.flatMap(c => c.value), wide = widen(regs, 15).filter(r => r.near_of);
  const hits = wide.map(r => ({ region: r, n: live.filter(x => !x.past && inRegion(facts.get(x.L.id), r)).length })).filter(x => x.n);
  return { base: regs.map(r => r.label), nearby: hits.slice(0, 6).map(x => ({ label: x.region.label, km: x.region.km, of: x.region.near_of, count: x.n })) };
}

// ---- 비교: 질문 속 단지 이름 → 공고 ----
export function findTargets(D, names, { past = true } = {}) {
  const rows = D.rows.filter(r => past || !r.past);
  const toks = s => String(s).replace(/\(.*?\)|아파트|단지|\d+,\d+단지/g, ' ').split(/[\s·,]+/).filter(w => w.length >= 2);
  return names.map(n => {
    const ws = toks(n);
    // 낱말이 모두 이름(또는 주소 — '도봉 한신'의 '도봉')에 있어야 같은 단지로 본다. 하나라도 없으면 다른 단지 ('도봉 한신' ≠ '의왕역 한신더휴')
    const scored = rows.map(r => ({ r, s: ws.filter(w => norm(r.L.name).includes(norm(w)) || norm((r.raw && r.raw.address) || '').includes(norm(w))).length / Math.max(1, ws.length), n: ws.filter(w => norm(r.L.name).includes(norm(w))).length })).filter(x => x.s === 1 && x.n >= 1);
    const best = Math.max(0, ...scored.map(x => x.s));
    let hit = scored.filter(x => x.s === best).map(x => x.r);
    if (hit.some(r => !r.past)) hit = hit.filter(r => !r.past);   // 지금 공고가 있으면 같은 이름의 지난 공고는 빼고 (지난 공고는 지금 공고가 없을 때만)
    return { query: n, rows: hit, found: hit.length > 0 };
  });
}

export const fmtEok = v => v == null ? '-' : (v >= 1 ? (Math.round(v * 100) / 100).toLocaleString('ko-KR') + '억' : Math.round(v * 10000).toLocaleString('ko-KR') + '만');
export const signed = v => v == null ? '-' : (v >= 0 ? '+' : '-') + fmtEok(Math.abs(v));
export { ELIG_WORD, GRADE_RANK };
