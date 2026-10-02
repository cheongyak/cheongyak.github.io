// AI 두 번: ① 조건 해석(질문 → 정해진 JSON) ② 설명(도구 결과만 받아 자연어로). 검색·판정·점수는 코드가 한다.
// AI 결과는 형식·내용 검사를 통과해야 쓰고, 막히면 규칙 해석·기본 답을 그대로 쓴다. 호출 함수(llm)는 밖에서 넣는다 — 나중에 chat/worker/src/llm.js callClaude.
import { understood } from './answer.mjs';

export const PROMPT_VERSION = 'v2-0.1';
const KEYS = ['region_in', 'region_out', 'price_max', 'price_min', 'price_range', 'area', 'households_min', 'not_single', 'rooms', 'station_walk', 'school_walk', 'commute', 'supply', 'status', 'eligible_only', 'margin', 'new_build'];
const WEIGHTS = ['required', 'preferred', 'explore'];

export function extractPrompt(question, ruleC) {
  const system = `너는 청약 질문을 검색 조건 JSON 으로 바꾸는 해석기다. 답은 JSON 하나만 쓴다.
형식: {"intent":"search|compare|explain|score","targets":[단지 이름],"conds":[{"key":..,"value":..,"weight":"required|preferred|explore","text":"질문 속 근거 낱말"}],"assume":{"married":bool,"cash":억,"income":만원,"homeless":bool,"kids":수},"perspectives":["price|margin|chance"],"unsupported":["형식 밖 조건"],"scope":{"past":bool}}
key 는 ${KEYS.join(', ')} 만 쓴다. 형식 밖 조건(급지·호재·학군·주차·층·향 등)은 conds 에 넣지 말고 unsupported 에 그대로 적는다.
weight: '꼭·반드시·필수·제외·싫어' = required, '좋겠다·선호·가능하면' = preferred, '아니어도 돼·고려·잘 몰라·근처' = explore.
지역 value 는 [{"sido":"서울","district":"송파구","label":"송파"}] 모양. 금액은 억 단위 숫자. 면적은 {"min":㎡,"max":㎡,"label":".."}.
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
  const C = { intent: j.intent || ruleC.intent, targets: j.targets || ruleC.targets, conds: j.conds, assume: j.assume || {}, perspectives: j.perspectives || [], unsupported: j.unsupported || [], scope: j.scope || { past: false }, q: ruleC.q };
  return { ok: true, C };
}

// 설명에 넘길 사실: 이것 밖의 단지명·숫자·판정은 답에 쓰면 안 된다
export function factsForLLM(C, r, compare, { profile }) {
  const pick = it => it && it.f ? { name: it.f.name, unit: it.f.unit, status: it.f.status, past: it.f.past, region: [it.f.sido, it.f.district].join(' '), area: it.f.area.v, price: it.f.price.v,
    margin: it.f.margin.g === 'unknown' ? null : { grade: it.f.margin.name, lo: round(it.f.margin.lo), hi: round(it.f.margin.hi), state: '추정' }, jeonse: it.f.jeonse.v ? round(it.f.jeonse.v) : null,
    complex: it.f.complex.state === '확인' ? { households: it.f.complex.households, buildings: it.f.complex.buildings } : null, station: it.f.station.state === '추정' ? { name: it.f.station.name, walk: it.f.station.walk, m: it.f.station.m } : null,
    school: it.f.school.state === '추정' ? { name: it.f.school.name, walk: it.f.school.walk, m: it.f.school.m } : null, elig: it.elig || null, sp_ok: (it.sp || []).filter(s => s.s === 'ok').map(s => s.label),
    competition: it.f.competition ? it.f.competition.rows : null, commute: (it.f.commute || []).filter(x => x.min != null).map(x => ({ to: x.place, who: x.who, car_min: x.min, km: x.km, src: x.src })), dates: it.f.dates, unknown: it.unknown || [], link: it.f.link } : null;
  return { understood: understood(C), profile, candidates: r.groups.slice(0, 5).map(g => ({ ...pick(g.best), others: g.types.slice(1).map(t => ({ unit: t.f.unit, price: t.f.price.v })) })), unsure: r.unsure.slice(0, 5).map(pick), excluded: r.excluded, relax: r.relax.map(o => ({ label: o.label, count: o.count })),
    explore: r.explore, perspectives: r.perspectives, compare: compare ? compare.map(t => ({ query: t.query, found: t.found, picks: (t.notices || []).map(n => ({ ...pick(n.pick), others: n.all })) })) : null,
    alternatives: (r.relax || []).flatMap(o => (o.groups || []).map(g => pick(g.best))).concat((r.nearMiss || []).map(g => pick(g.best))), total: r.total };
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
DRAFT 는 같은 사실로 만든 기본 답이다. 사실은 DRAFT 와 같게 두고, 읽기 좋게 다듬고 '왜 이 순서인지'를 설명한다.`;
  const user = `QUESTION: ${question}\nFACTS: ${JSON.stringify(facts)}\nDRAFT:\n${draft}`;
  return { system, user };
}

// 설명 검사: 단지명·숫자·판정·과거 표시가 FACTS 와 같은지, 데이터 없는 주제를 단정하지 않는지
export function checkAnswer(ans, facts) {
  const flags = [], a = String(ans || '');
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
