// 청약봇 V2 한 바퀴: 질문 → 조건 추출(규칙, 있으면 AI) → 필수/선호/탐색 → 실제 데이터 검색 → 후보 → 걸러내기 → 추천·비교 → 설명(기본 답, 있으면 AI).
// 지금 청약패스 화면·서버와 연결돼 있지 않다. 나중에 청약봇 서버(chat/worker)가 ask() 를 부르고 스위치 chatbot_v2 로 켠다 (README.md).
import { extract, applyDelta } from './extract.mjs';
import { search, findTargets, factsOf, resolvePlaces } from './search.mjs';
import { compose, buildCompare, understood } from './answer.mjs';
import { extractPrompt, parseExtraction, explainPrompt, factsForLLM, checkAnswer } from './llm.mjs';
import { SP_LABEL } from './lexicon.mjs';

// llm: async ({system, user}) => text  (없으면 AI 없이). profile: 청약패스 '내 조건'(브라우저 저장값) 그대로. state: 지난 질문의 조건(대화 중 조건 유지)
// D: 데이터 묶음 (Node: node.mjs, 브라우저: browser.mjs fromScreen). 이 파일은 Node·브라우저 어디서나 돈다 (fs·네트워크 안 씀)
// commute: async (from{lat,lng}, to{lat,lng}) => {min, km, src, at} | {error}  (서버에서만 — commute.mjs carTime). 없으면 직선거리만
// geocode: async (장소 이름) => {name, lat, lng} | {error} — 표에 없는 직장 위치를 실제 장소로 (서버에서만, 카카오 장소 검색)
export async function ask({ D, question, profile = null, state = null, llm = null, updated = '', commute = null, geocode = null }) {
  const t0 = Date.now(), steps = [];
  // 1. 조건 추출 — 규칙 해석을 먼저, AI 가 있으면 AI 해석을 쓰되 형식 검사를 통과한 것만
  let C = state ? applyDelta(state, question) : extract(question), via = 'rules';
  if (llm && !state) {
    try {
      const { system, user } = extractPrompt(question, C);
      const got = parseExtraction(await llm({ system, user, purpose: 'extract' }), C);
      if (got.ok) { C = got.C; via = 'ai'; } else steps.push('AI 조건 해석 거절: ' + got.why);
    } catch (e) { steps.push('AI 조건 해석 실패: ' + String(e.message || e).slice(0, 80)); }
  }
  C.today = D.today;
  resolvePlaces(D, C);   // '정자역'·'군자역' 같은 역 이름 출퇴근지 좌표는 노선 자료(OpenStreetMap)에서
  if (geocode) for (const c of C.conds.filter(c => c.key === 'commute' && (c.value.approx || c.value.lat == null))) {   // '구로구 (중심 근사)' → 실제 장소 (예: 구로구청)
    const word = c.value.place.replace(/\s?\([^)]*중심 근사\)/, ''), q = /(구|시|군)$/.test(word) ? word + '청' : word, g = await geocode(q);   // '구로구'만 찾으면 구 안의 아무 장소(푸른수목원)가 나와 구청으로 찾는다 (2026-10-02 확인)
    if (g && !g.error) { Object.assign(c.value, { place: word, lat: g.lat, lng: g.lng, approx: false, found: g.name }); c.text = (c.value.who ? c.value.who + ' ' : '') + '직장 ' + word + '(' + g.name + ' 기준)'; }
  }
  steps.push('조건 ' + C.conds.length + '개 (' + via + ')');
  // 2~6. 검색·걸러내기·자격·점수
  let mode = C.intent === 'compare' && C.targets.length >= 2 ? 'compare' : C.intent === 'explain' ? 'explain' : 'search';
  const r = search(D, C, { profile });
  let compare = null;
  if (mode === 'compare') {
    const tg = findTargets(D, C.targets, { past: true });
    compare = buildCompare(D, tg, C, { profile });
    const p = profile ? D.profileOf(Object.assign({}, profile)) : null;
    for (const t of compare) for (const n of (t.notices || [])) {
      n.pick.f = factsOf(D, n.pick.row);
      if (p && !n.pick.row.noJudge) { n.pick.elig = D.E.eligBucket(n.pick.row.L, p); n.pick.sp = D.E.spTypesFor(n.pick.row.L).map(t => ({ type: t, label: SP_LABEL[t] || t, s: D.E.spJudge(n.pick.row.L, p, t).s })); }
    }
  }
  if (r.explore) r.explore.nearby.sort((a, b) => a.km - b.km);
  // 출퇴근 시간: 보여 줄 후보(상위 5곳·대안·확인 필요)만 실시간 조회 — 저장하지 않는다(카카오 이용 조건). 순서는 시간으로 다시 매긴다
  const cms = C.conds.filter(c => c.key === 'commute' && c.value.lat != null && !c.value.via_shuttle);
  if (commute && cms.length) {
    const its = [...r.groups.slice(0, 5).map(g => g.best), ...r.unsure.slice(0, 4), ...(r.relax || []).flatMap(o => (o.groups || []).map(g => g.best)), ...(r.nearMiss || []).map(g => g.best)].filter(it => it.f.geo);
    await Promise.all(its.map(async it => { it.f.commute = await Promise.all(cms.map(async c => ({ place: c.value.place, who: c.value.who || '', ...(await commute(it.f.geo, c.value)) }))); }));
    r.commuted = its.some(it => it.f.commute.some(x => x.min != null));
    const avg = it => { const t = (it.f.commute || []).filter(x => x.min != null); return t.length ? t.reduce((a, b) => a + b.min, 0) / t.length : 999; };
    if (r.commuted) r.groups.sort((a, b) => (b.best.elig ? { ok: 3, unsure: 2, r2: 1, no: 0 }[b.best.elig] : 0) - (a.best.elig ? { ok: 3, unsure: 2, r2: 1, no: 0 }[a.best.elig] : 0) || avg(a.best) - avg(b.best));
    steps.push('출퇴근 조회 ' + its.length + '곳');
  }
  steps.push('후보 ' + r.ok.length + ' · 확인 필요 ' + r.unsure.length + ' · 제외 ' + Object.values(r.excluded).reduce((a, b) => a + b, 0));
  // 7. 설명 — 기본 답은 항상 만든다(AI 실패·한도 초과 때 그대로 나감)
  const base = mode === 'explain' ? null : compose(C, r, { profile: !!profile, updated: updated || D.today, mode, compare });
  let text = base, how = 'template';
  const facts = factsForLLM(C, r, compare, { profile: !!profile });
  if (llm && base) {
    try {
      const { system, user } = explainPrompt(question, facts, base);
      const ans = await llm({ system, user, purpose: 'explain' });
      const chk = checkAnswer(ans, facts);
      if (chk.ok) { text = ans; how = 'ai'; } else steps.push('AI 설명 거절: ' + chk.flags.slice(0, 3).join(' / '));
    } catch (e) { steps.push('AI 설명 실패: ' + String(e.message || e).slice(0, 80)); }
  }
  return { mode, text, how, state: C, understood: understood(C), result: summarize(r, compare), facts, steps, ms: Date.now() - t0,
    legacy: mode === 'explain' ? '제도 설명 질문 — 지금은 기존 청약봇(법령·공고문 근거)으로 넘김. 검증한 설명집은 STEP 3' : null };
}

// 화면 카드용 요약 (나중에 청약패스 화면이 그린다)
function summarize(r, compare) {
  const c = it => ({ id: it.f.id, name: it.f.name, unit: it.f.unit, price: it.f.price.v, area: it.f.area.v, status: it.f.status, past: it.f.past, elig: it.elig || null,
    sp_ok: (it.sp || []).filter(s => s.s === 'ok').map(s => s.label), margin: it.f.margin.g, unknown: it.unknown || [], link: it.f.link });
  return { total: r.total, excluded: r.excluded, candidates: r.groups.map(g => c(g.best)), unsure: r.unsure.map(c), refused: r.refused.map(c), perspectives: r.perspectives, relax: r.relax.map(o => ({ label: o.label, count: o.count })),
    explore: r.explore, compare: compare && compare.map(t => ({ query: t.query, found: t.found, picks: (t.notices || []).map(n => c(n.pick)) })) };
}
