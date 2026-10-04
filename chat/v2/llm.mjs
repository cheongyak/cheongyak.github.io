// AI 두 번: ① 조건 해석(질문 → 정해진 JSON) ② 설명(도구 결과만 받아 자연어로). 검색·판정·점수는 코드가 한다.
// AI 결과는 형식·내용 검사를 통과해야 쓰고, 막히면 규칙 해석·기본 답을 그대로 쓴다. 호출 함수(llm)는 밖에서 넣는다 — 나중에 chat/worker/src/llm.js callClaude.
import { understood } from './answer.mjs';
import { distKm } from './lexicon.mjs';

export const PROMPT_VERSION = 'v2-0.2';   // 0.2: DRAFT 의 카드·줄 순서를 그대로 두고 첫머리와 '왜 이곳'만 다듬기 (AI 품질 회차 1: 0.1 은 기본 답에 3승 6패 11무 — 후보를 빼거나 같은 말을 반복)
const KEYS = ['region_in', 'region_out', 'price_max', 'price_min', 'price_range', 'area', 'households_min', 'not_single', 'rooms', 'station_walk', 'school_walk', 'commute', 'supply', 'status', 'eligible_only', 'margin', 'new_build', 'line', 'near_station'];
const WEIGHTS = ['required', 'preferred', 'explore'];

export function extractPrompt(question, ruleC) {
  const system = `너는 청약 질문을 검색 조건 JSON 으로 바꾸는 해석기다. 답은 JSON 하나만 쓴다.
형식: {"intent":"search|compare|explain|score","targets":[단지 이름],"conds":[{"key":..,"value":..,"weight":"required|preferred|explore","text":"질문 속 근거 낱말"}],"assume":{"married":bool,"cash":억,"income":만원,"homeless":bool,"kids":수,"family":가족 수,"no_school":bool},"perspectives":["price|margin|chance"],"unsupported":["형식 밖 조건"],"scope":{"past":bool,"expand":bool}}
key 는 ${KEYS.join(', ')} 만 쓴다. 형식 밖 조건(급지·호재·학군·주차·층·향 등)은 conds 에 넣지 말고 unsupported 에 그대로 적는다.
weight: '꼭·반드시·필수·제외·싫어' = required, '좋겠다·선호·가능하면' = preferred, '아니어도 돼·고려·잘 몰라·근처' = explore.
지역 value 는 [{"sido":"서울","district":"송파구","label":"송파"}] 모양. 금액은 억 단위 숫자. 면적은 {"min":㎡,"max":㎡,"label":".."}.
노선(신분당선·9호선 등)은 지역이 아니다 — key "line", value {"line":"신분당선","m":1000}. '신분당선'의 '분당'을 지역으로 읽지 않는다. 'A 말고도·같은 조건으로'는 제외가 아니라 scope.expand=true.
아래 '규칙 해석'이 이미 찾은 조건을 기준으로, 빠진 조건·잘못 나눈 무게만 고친다. 질문에 없는 조건을 만들지 않는다.`;
  const user = `질문: ${question}\n규칙 해석: ${JSON.stringify({ intent: ruleC.intent, targets: ruleC.targets, conds: ruleC.conds, assume: ruleC.assume, unsupported: ruleC.unsupported, scope: ruleC.scope })}`;
  return { system, user };
}

// AI 조건 해석 검사: 형식, 허용 key, 질문에 근거(text)가 있는지, 규칙 해석이 찾은 필수 조건을 지우지 않았는지
export function parseExtraction(text, ruleC) {
  let j;
  try { j = JSON.parse(String(text).replace(/^```(json)?|```$/g, '').trim()); } catch (e) { return { ok: false, why: 'JSON 아님' }; }
  if (!j || !Array.isArray(j.conds)) return { ok: false, why: 'conds 없음' };
  const q = (ruleC.q || '').replace(/\s+/g, '');
  for (const c of j.conds) {
    if (!KEYS.includes(c.key)) return { ok: false, why: '모르는 조건 ' + c.key };
    if (!WEIGHTS.includes(c.weight)) return { ok: false, why: '무게 값 ' + c.weight };
    const t = String(c.text || '').replace(/\s+/g, '').replace(/(제외|이하|이상|필수|출퇴근)$/, '');
    if (t && !q.includes(t.slice(0, Math.min(3, t.length)))) return { ok: false, why: '질문에 없는 조건: ' + c.text };
  }
  for (const c of ruleC.conds.filter(c => c.weight === 'required' && ['region_out', 'price_max', 'not_single', 'eligible_only'].includes(c.key)))
    if (!j.conds.some(x => x.key === c.key)) return { ok: false, why: '규칙 해석의 필수 조건을 지움: ' + c.key };
  const C = { intent: j.intent || ruleC.intent, targets: j.targets || ruleC.targets, conds: j.conds, assume: { ...(ruleC.assume || {}), ...(j.assume || {}) }, perspectives: [...new Set([...(ruleC.perspectives || []), ...(j.perspectives || [])])], unsupported: j.unsupported || [], scope: { ...(ruleC.scope || {}), ...(j.scope || {}) }, q: ruleC.q, plan: j.plan || ruleC.plan, limit: ruleC.limit, targetArea: ruleC.targetArea };   // 규칙이 찾은 넓혀 보기·가족 수·학군 안 따짐을 AI 가 빠뜨려도 남김
  // 규칙이 찾은 출퇴근지의 위치 정보(역 이름·셔틀 정류장·좌표)와 역 주변 조건은 AI 결과에 이어 붙인다 (카톡 실제 질문 2026-10-04)
  for (const c of C.conds.filter(c => c.key === 'commute' && c.value)) { const r0 = ruleC.conds.find(x => x.key === 'commute' && (x.value.place === c.value.place || String(x.value.place).includes(String(c.value.place).replace(/역$/, '')) || String(c.value.place).includes(String(x.value.place).replace(/\s?\(.*$/, '').replace(/역$/, ''))));
    if (r0) c.value = { ...r0.value, max_min: c.value.max_min != null ? c.value.max_min : r0.value.max_min, who: c.value.who || r0.value.who }; }
  for (const r0 of ruleC.conds.filter(x => x.key === 'near_station' || (x.key === 'commute' && (x.value.who === '셔틀 정류장' || x.value.via_shuttle)))) if (!C.conds.some(c => c.key === r0.key && JSON.stringify(c.value.names || c.value.place) === JSON.stringify(r0.value.names || r0.value.place))) C.conds.push(r0);
  for (const u of ruleC.unsupported || []) if (/^(매물 등급|사고팔 시점|얼마까지 대출)/.test(u) && !C.unsupported.includes(u)) C.unsupported.push(u);
  return { ok: true, C };
}

// 설명에 넘길 사실: 이것 밖의 단지명·숫자·판정은 답에 쓰면 안 된다
export function factsForLLM(C, r, compare, { profile }) {
  const pick = it => it && it.f ? { name: it.f.name, unit: it.f.unit, status: it.f.status, past: it.f.past, region: [it.f.sido, it.f.district].join(' '), area: it.f.area.v, price: it.f.price.v,
    margin: it.f.margin.g === 'unknown' ? null : { grade: it.f.margin.name, lo: round(it.f.margin.lo), hi: round(it.f.margin.hi), state: '추정' }, jeonse: it.f.jeonse.v ? round(it.f.jeonse.v) : null,
    complex: it.f.complex.state === '확인' ? { households: it.f.complex.households, buildings: it.f.complex.buildings } : null, station: it.f.station.state === '추정' ? { name: it.f.station.name, walk: it.f.station.walk, m: it.f.station.m } : null,
    school: it.f.school.state === '추정' ? { name: it.f.school.name, walk: it.f.school.walk, m: it.f.school.m } : null, elig: it.elig || null, sp_ok: (it.sp || []).filter(s => s.s === 'ok').map(s => s.label),
    competition: it.f.competition ? it.f.competition.rows : null, budget_slack: (() => { const pm = C.conds.find(c => c.key === 'price_max'); return pm && it.f.price.v != null ? round(pm.value - it.f.price.v) : null; })(), units: { general: it.f.units.general, special: it.f.units.special, total: it.f.units.general + it.f.units.special }, line_km: it.f.geo ? C.conds.filter(c => c.key === 'commute' && c.value.lat != null).map(c => ({ to: c.value.place, km: Math.round(distKm(it.f.geo, c.value)) })) : [], limits: it.f.limits ? { residence_duty_years: it.f.limits.duty, rewin_years: it.f.limits.rewin, price_cap: it.f.limits.priceCap } : null, near_station: it.f.nearSt ? { station: it.f.nearSt.name, m: it.f.nearSt.m, km: Math.round(it.f.nearSt.m / 100) / 10 } : null, rail_line: it.f.line ? Object.entries(it.f.line).map(([ln, n]) => ({ line: ln, station: n.name, m: n.m, km: Math.round(n.m / 100) / 10 })) : [], commute: (it.f.commute || []).filter(x => x.min != null).map(x => ({ to: x.place, who: x.who, car_min: x.min, km: x.km, src: x.src })), dates: it.f.dates, unknown: it.unknown || [], link: it.f.link } : null;
  return { understood: understood(C), cond_values: C.conds.filter(c => typeof c.value === 'number' || (c.value && (c.value.min != null || c.value.bed != null))).map(c => ({ key: c.key, value: c.value })), profile, candidates: r.groups.slice(0, 5).map(g => ({ ...pick(g.best), others: g.types.slice(1).map(t => ({ unit: t.f.unit, price: t.f.price.v })) })), rest: r.groups.slice(5, 15).map(g => ({ name: g.name, unit: g.best.f.unit, price: g.best.f.price.v, elig: g.best.elig || null })), unsure: (() => { const m = new Map(); r.unsure.forEach(x => { if (!m.has(x.f.nid)) m.set(x.f.nid, x); }); return [...m.values()].slice(0, 8).map(pick); })(), excluded: r.excluded, relax: r.relax.map(o => ({ label: o.label, count: o.count })),
    explore: r.explore, perspectives: r.perspectives, compare: compare ? compare.map(t => ({ query: t.query, found: t.found, picks: (t.notices || []).map(n => ({ ...pick(n.pick), others: n.all })) })) : null,
    alternatives: (r.relax || []).flatMap(o => (o.groups || []).map(g => ({ ...pick(g.best), from_region_km: (() => { const regs = C.conds.filter(c => c.key === 'region_in').flatMap(c => c.value).filter(v => v.lat); return regs.length && g.best.f.geo ? Math.round(Math.min(...regs.map(v => distKm(g.best.f.geo, v)))) : null; })() }))).concat((r.nearMiss || []).map(g => pick(g.best))).concat((r.closest || []).map(x => ({ ...pick(x), near_km: x.km, misses: x.misses }))), total: r.total,
    outside: r.outside ? { base: r.outside.base, total: r.outside.total, picks: r.outside.groups.map(g => ({ ...pick(g.best), from_region_km: g.best.km })) } : null,   // 'A 말고도 같은 조건으로' 블록 (샘플 3)
    rail_lines: r.lineInfo || [], plan: C.plan || null,
    question_numbers: [...new Set((String(C.q || '').match(/\d+(?:\.\d+)?/g) || []).map(Number))],   // 질문자가 직접 말한 숫자(예산 17.5억 등)는 답에 다시 써도 된다 (AI 회차 6: 'FACTS 에 없는 숫자 17.5'로 막힘)   // 노선 역세권 공고 현황 (샘플 4)
    constants: { size_hint_m2: [59, 84], newborn_age: 2, max_cards: 5, line_m: [1000, 3000] } };   // 답 틀에 늘 들어가는 고정 숫자 (20평대=전용 59㎡ 안내, 신생아 특공 2세 미만)
}
const round = v => v == null ? null : Math.round(v * 100) / 100;

export function explainPrompt(question, facts, draft) {
  const system = `너는 청약패스의 청약 도우미다. FACTS(청약패스 데이터·판정 엔진 결과)만 써서 질문에 답한다.
말투: 해요체, 친근하지만 군더더기 없이. 순서: 질문을 받는 한 줄 → [이렇게 이해했어요] → '결론부터 말씀드리면,' 한두 문장 → [후보별 핵심 지표](후보마다 이름·지역·면적·단지 규모 한 줄, 그 아래 '· 항목  값 (출처)' 줄) → [관점별로 보면] → [확인하지 못한 것] → [다음에 해볼 것].
규칙:
- 판정(신청 가능·확인 필요·2순위만·신청 불가)은 FACTS 의 elig 그대로. 새로 판정하지 않는다. 지난 공고는 '그때 넣었다면'으로만.
- 숫자·단지명은 FACTS 에 있는 것만. 시세 차익·전세·거리는 '추정'이라고 쓴다. 없는 값은 '확인 불가'.
- 급지·호재·상승 여력·학군·주차처럼 FACTS 에 없는 것은 추측하지 말고 '청약패스에 데이터가 없어요'라고 한 줄로.
- 조건에 맞는 공고가 없으면 '없다'고 분명히 쓰고, 왜 없는지(excluded), 바꾸면 생기는 조건(relax), 가까운 지역(explore), 새 공고 알림 순서로.
- 각 후보 끝에 link 를 그대로 붙인다.
DRAFT 는 같은 사실로 만든 기본 답이다. 고치는 곳은 두 군데뿐이다:
 (1) 첫머리: 질문자의 상황을 한 문장으로 짚고, '결론부터 말씀드리면'으로 시작하는 2~3문장 — 갈래가 있으면 '~가 우선이면 A, ~가 우선이면 B'.
 (2) 후보마다 '→' 로 시작하는 '왜 이곳' 한두 문장 — 질문자 조건(아이·직장·예산)과 이어서.
그 밖의 줄(대괄호 제목, '· 항목  값 (출처)' 지표 줄, 링크, 나머지 목록, 다음에 해볼 것)은 DRAFT 그대로 둔다. 후보를 빼거나 더하지 말고, 지표 줄의 숫자를 문장에서 다시 되풀이하지 않는다. 표(|)는 쓰지 않는다(휴대폰).`;
  const user = `QUESTION: ${question}\nFACTS: ${JSON.stringify(facts)}\nDRAFT:\n${draft}`;
  return { system, user };
}

// 설명 검사: 단지명·숫자·판정·과거 표시가 FACTS 와 같은지, 데이터 없는 주제를 단정하지 않는지
export function checkAnswer(ans, facts) {
  const flags = [], a = String(ans || '').replace(/https?:\/\/\S+/g, ' ');   // 링크 속 숫자(%20 등)는 검사하지 않음
  if (a.length < 40) flags.push('답이 너무 짧음');
  const all = [...(facts.candidates || []), ...(facts.unsure || []), ...((facts.compare || []).flatMap(t => t.picks || []))].filter(Boolean);
  const blob = JSON.stringify(facts);
  // 숫자: 억·㎡·세대·분·% 붙은 숫자는 FACTS 에 있어야 (반올림 표기 허용)
  const nums = [...a.matchAll(/(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?(억|㎡|세대|분|%|km|m\b)/g)].map(m => +m[1].replace(/,/g, ''));
  const pool = [...blob.matchAll(/-?\d+(?:\.\d+)?/g)].map(m => Math.abs(+m[0]));
  for (const n of nums) if (!pool.some(v => Math.abs(v - n) < 0.051 || Math.abs(Math.round(v * 10) / 10 - n) < 0.001 || Math.abs(v * 10000 - n) < 1)) flags.push('FACTS 에 없는 숫자 ' + n);
  // 판정: 후보 이름 근처에 다른 판정을 쓰면
  for (const c of all) if (c.elig) {
    const want = { ok: '신청 가능', unsure: '확인 필요', r2: '2순위', no: '불가' }[c.elig];
    for (let i = a.indexOf(c.name); i >= 0; i = a.indexOf(c.name, i + 1)) {
      const seg = a.slice(i, i + 420);
      if (!seg.slice(0, 90).includes(c.unit)) continue;   // 같은 공고 다른 주택형은 판정이 다를 수 있다 — 주택형까지 같은 자리만 본다
      const card = seg.split('\n\n')[0];
      const m = card.match(/(일반공급|신혼희망타운|무순위|특별공급 기준) (신청 가능|확인 필요|2순위만|신청 불가)/);
      if (m && !m[2].includes(want)) flags.push(c.name + ' ' + c.unit + ' 판정 불일치');
      if (c.past && /접수 중|지금 신청/.test(card)) flags.push(c.name + ' 과거 공고를 지금처럼 씀');
    }
  }
  // 데이터 없는 주제 단정
  if (/(\d급지|급지(는|가) \S+|호재(는|가|로) )/.test(a) && !/데이터가 없/.test(a)) flags.push('데이터 없는 급지·호재를 단정');
  if (/(반드시 당첨|무조건 당첨|확실히 오를)/.test(a)) flags.push('단정 표현');
  return { ok: flags.length === 0, flags };
}
