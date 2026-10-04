// 청약봇 답 품질 채점기 (2026-10-03, 사용자 '답변 품질 검증 알고리즘 → 높일 방법 → 지속적으로 진화').
// 7개 차원 × 검사 항목. 각 항목은 0~1 점과 이유를 낸다. 치명(hard) 항목이 하나라도 실패하면 그 답은 0점(틀린 답은 아무리 친절해도 0점).
// 기준은 STYLE.md(사용자 예시 답에서 뽑은 원칙)와 CLAUDE.md(출처·추정 표시, 지어내지 않기). 기대 조건(expect)이 있으면 '이해' 차원도 잰다.
import { checkAnswer } from '../llm.mjs';

export const DIMS = { 정확: 0.30, 이해: 0.15, 완결: 0.15, 개인화: 0.10, 정직: 0.15, 실용: 0.10, 읽기: 0.05 };

const lines = t => String(t || '').split('\n');
const has = (t, re) => re.test(t);
const ratio = (n, d) => d ? Math.max(0, Math.min(1, n / d)) : 1;
// 후보 카드: '이름 (지역 · 전용 …㎡(…) · …)' 로 시작해 빈 줄까지
export function cards(text) {
  const out = [];
  for (const block of String(text).split(/\n\n+/)) { const first = block.split('\n')[0]; if (/^[^\[·→].*\(.*(전용|㎡).*\)$/.test(first) && /·\s/.test(block)) out.push(block); }
  return out;
}

// 조건 비교: 기대 조건 목록 vs 해석 결과 → 재현율(빠뜨림)·정밀도(엉뚱하게 만든 조건)
// 조건 비교 — 대화형 검색 봇의 표준 지표: 슬롯 단위 TP/FP/FN(→ F1)과 Joint Goal Accuracy(한 질문의 조건을 전부 맞혀야 1, MultiWOZ DST 지표).
// 기대 조건이 '전부'인 질문(strict, 생성 질문)만 FP 를 센다. 사람이 쓴 시험지는 일부만 적어 FP·JGA 를 재지 않는다.
export function condMatch(expect, C) {
  if (!expect || !expect.conds) return null;
  const hit = (e, c) => c.key === e.key && (!e.weight || c.weight === e.weight) && (e.value === undefined || JSON.stringify(c.value) === JSON.stringify(e.value))
    && (!e.label || (Array.isArray(c.value) && c.value.some(v => v.label === e.label))) && (!e.place || c.value.place === e.place) && (!e.who || c.value.who === e.who);
  // 지역은 한 조건에 여러 곳이 들어간다 → 지역 하나 = 슬롯 하나로 센다
  const slots = C.conds.flatMap(c => (c.key === 'region_in' || c.key === 'region_out') && Array.isArray(c.value) ? [...new Set(c.value.map(v => v.label))].map(l => ({ ...c, value: c.value.filter(v => v.label === l) })) : [c]);
  const used = new Set(), tp = [], fn = [];
  for (const e of expect.conds) { const i = slots.findIndex((c, k) => !used.has(k) && hit(e, c)); if (i >= 0) { used.add(i); tp.push(e); } else fn.push(e); }
  const fp = expect.strict ? slots.filter((c, k) => !used.has(k) && !(expect.allow || []).includes(c.key)) : [];
  const bad = (expect.not || []).filter(e => slots.some(c => hit(e, c))).length;
  const assumeOk = Object.entries(expect.assume || {}).every(([k, v]) => (C.assume || {})[k] === v);
  return { tp: tp.length, fp: fp.length + bad, fn: fn.length, jga: expect.strict ? (fn.length === 0 && fp.length === 0 && !bad && assumeOk ? 1 : 0) : null,
    recall: ratio(tp.length, expect.conds.length), precision: ratio(tp.length, tp.length + fp.length + bad), missed: fn, extra: fp.map(c => c.key + (Array.isArray(c.value) && c.value[0] && c.value[0].label ? ':' + c.value[0].label : '')), forbidden: bad, assumeOk };
}

export function score({ q, a, expect = null }) {
  const t = a.text || '', C = a.state || { conds: [], assume: {} }, F = a.facts || {}, R = a.result || {};
  const items = [];
  const add = (dim, id, s, why, hard = false) => items.push({ dim, id, s: Math.max(0, Math.min(1, s)), why: s < 1 ? why : '', hard });
  const cs = cards(t), nCards = cs.length, mode = a.mode;
  const noResult = /청약은 없어요/.test(t);

  // ---- 정확 (치명) ----
  const chk = checkAnswer(t, F);
  add('정확', 'facts', chk.ok ? 1 : 0, '사실 묶음과 다른 숫자·판정: ' + chk.flags.slice(0, 3).join(' / '), true);
  const pastBad = cs.filter(c => /마감된 과거 공고/.test(c) && /접수 중|신청 가능해요/.test(c.split('\n')[0] + (c.match(/→.*/) || [''])[0])).length;
  add('정확', 'past', pastBad ? 0 : 1, '과거 공고를 지금 신청 가능처럼 씀', true);
  const eligLine = cs.filter(c => /· 내 자격/.test(c)).length;
  add('정확', 'elig-shown', !a.profileGiven || mode === 'compare' || nCards === 0 ? 1 : ratio(eligLine, nCards), '내 조건이 있는데 후보에 내 자격 줄이 없음', false);
  add('정확', 'not-legacy', mode === 'explain' ? 1 : t ? 1 : 0, '답이 비어 있음', true);

  // ---- 이해 ----
  const m = condMatch(expect, C);
  if (m) { add('이해', 'recall', m.recall, '빠뜨린 조건: ' + m.missed.map(e => e.key + (e.label ? ':' + e.label : '') + (e.weight ? '(' + e.weight + ')' : '')).join(', '));
    add('이해', 'precision', m.precision, '엉뚱한 조건: ' + m.extra.join(','));
    if (m.jga != null) add('이해', 'jga', m.jga, '조건을 전부 맞히지 못함' + (m.assumeOk ? '' : ' (가정 틀림)')); }
  add('이해', 'echo', has(t, /\[이렇게 이해했어요\]\n·/) ? 1 : 0, "'이렇게 이해했어요'에 이해한 조건이 없음");
  const asked = (C.unsupported || []).length;
  add('이해', 'unsupported-said', asked ? (has(t, /데이터가 없어|예측하지 않아요|미리 뺄 수 없어요/) ? 1 : 0) : 1, '못 보는 조건(급지·주차 등)을 언급하지 않음');

  // ---- 완결 ----
  add('완결', 'conclusion', mode === 'compare' ? (has(t, /결론부터|찾지 못했어요/) ? 1 : 0) : (has(t, /결론부터 말씀드리면|청약은 없어요/) ? 1 : 0), '결론 문장이 없음');
  if (nCards) {
    add('완결', 'card-source', ratio(cs.filter(c => /\(청약홈\)/.test(c)).length, nCards), '출처(청약홈) 없는 후보 카드');
    add('완결', 'card-link', ratio(cs.filter(c => /https:\/\/cheongyakpass\.kr\/#\/detail\//.test(c)).length, nCards), '자세히 보기 링크 없는 카드');
    add('완결', 'card-core', ratio(cs.filter(c => /· 일정/.test(c) && /· (분양가|임대보증금)/.test(c)).length, nCards), '일정·분양가 줄 없는 카드');
  }
  if (noResult) add('완결', 'no-result-flow', [/왜 없는지/, /바꾸면 생겨요|대신 눈여겨볼|가까운 지역|가장 가까운 곳/, /새 공고 알림/].filter(re => re.test(t)).length / 3, "결과 없음 흐름(왜 없는지·대안·알림) 일부 빠짐");
  add('완결', 'next', has(t, /\[다음에 해볼 것\]\n·/) ? 1 : 0, "'다음에 해볼 것' 없음");

  // ---- 개인화 ----
  const as = C.assume || {}, who = (C.conds || []).filter(c => c.key === 'commute' && c.value.who);
  const head = lines(t).slice(0, 3).join(' ');
  if (as.kids) { add('개인화', 'kids-opening', /아이/.test(head) ? 1 : 0, '아이 이야기를 첫머리에서 짚지 않음'); add('개인화', 'kids-school', nCards ? ratio(cs.filter(c => /· 초등학교/.test(c)).length, nCards) : 1, '아이가 있는데 초등학교 거리 줄이 없음'); }
  if (who.length) { add('개인화', 'commute-opening', who.every(c => head.includes(c.value.who)) ? 1 : 0, '두 분 직장을 첫머리에서 짚지 않음'); add('개인화', 'commute-card', nCards ? ratio(cs.filter(c => /· 출퇴근/.test(c)).length, nCards) : 1, '직장이 있는데 출퇴근 줄이 없는 카드'); }
  if ((C.conds || []).some(c => /^price/.test(c.key))) add('개인화', 'budget-basis', /예산/.test(head) ? 1 : 0, '예산을 기준으로 따졌다고 말하지 않음');
  if (nCards && mode !== 'compare') add('개인화', 'reasons', ratio(cs.filter(c => /\n→ /.test(c)).length, nCards), "후보마다 '왜 이곳' 한 줄이 없음");

  // ---- 정직 ----
  const mLines = t.match(/· 시세 차익 .*/g) || [];
  add('정직', 'margin-est', ratio(mLines.filter(l => /추정|확인 불가/.test(l)).length, mLines.length), "시세 차익에 '추정' 표시 없음", true);
  const dLines = t.match(/· (역|초등학교) .*/g) || [];
  add('정직', 'dist-est', ratio(dLines.filter(l => /추정|직선|확인 불가/.test(l)).length, dLines.length), "거리에 '추정·직선' 표시 없음");
  add('정직', 'no-hype', has(t.replace(/https?:\/\/\S+/g, ''), /(반드시|무조건|확실히)\s?(당첨|오를|올라)|100%/) ? 0 : 1, '과장 표현', true);
  const cm = (C.conds || []).filter(c => c.key === 'commute');
  if (cm.length) add('정직', 'commute-honest', has(t, /\d+분\(.*조회\)|시간 확인 불가|직선거리로만|경로 조회/) ? 1 : 0, '출퇴근 시간 근거(조회 시각) 또는 확인 불가 표시 없음');
  add('정직', 'disclaimer', has(t, /모집공고문을 꼭 확인/) ? 1 : 0, '신청 전 모집공고문 확인 안내 없음');

  // ---- 실용 ----
  const concl = lines(t).findIndex(l => /결론부터|청약은 없어요/.test(l));
  add('실용', 'conclusion-early', concl < 0 ? 0 : concl <= 12 ? 1 : 0.5, '결론이 너무 아래(12줄 뒤)');
  if (nCards >= 2 && mode !== 'compare' && /조건에 맞는 곳은/.test(t)) add('실용', 'scenarios', has(t, /\[이런 분께는 이곳\]/) ? 1 : 0.5, "'이런 분께는 이곳'(우선순위별 추천) 없음");
  add('실용', 'narrow-q', has(t, /알려 주시면|어느 쪽에|\[.*비교\]/) ? 1 : 0.5, '좁혀 줄 질문이 없음');
  if (nCards > 6) add('실용', 'not-too-many', 0.5, '후보가 너무 많음(6곳 넘음)');

  // ---- 읽기 ----
  add('읽기', 'length', t.length <= 4500 ? 1 : t.length <= 6500 ? 0.6 : 0.2, '너무 김(' + t.length + '자)');
  const ls = lines(t).filter(Boolean), long = ls.filter(l => l.length > 140 && !/^https?:/.test(l)).length;
  add('읽기', 'line', 1 - ratio(long, ls.length) * 3, '140자 넘는 줄 ' + long + '개');
  add('읽기', 'tone', has(t, /(합니다|습니다|십시오)[.!]?(\n|$)/) ? 0.3 : 1, '해요체가 아닌 문장');
  const free = ls.filter(l => !/^[·→]|^https?:|^\(/.test(l));   // 카드 지표 줄은 카드마다 같을 수 있어 빼고, 설명 문장만 반복을 센다
  const dup = free.length - new Set(free).size;
  add('읽기', 'dup', 1 - ratio(dup, free.length) * 4, '같은 줄 반복 ' + dup + '개');
  add('읽기', 'empty-section', has(t, /\]\n\n\[|\]\n*$/) ? 0 : 1, '내용 없는 칸');

  // 합계
  const dims = {}; for (const d of Object.keys(DIMS)) { const xs = items.filter(i => i.dim === d); dims[d] = xs.length ? xs.reduce((s, i) => s + i.s, 0) / xs.length : 1; }
  const hardFail = items.filter(i => i.hard && i.s < 1);
  const total = hardFail.length ? 0 : Math.round(Object.entries(DIMS).reduce((s, [d, w]) => s + w * dims[d], 0) * 1000) / 10;
  return { q, total, dims, slots: m ? { tp: m.tp, fp: m.fp, fn: m.fn, jga: m.jga } : null, hardFail: hardFail.map(i => i.id + ': ' + i.why), issues: items.filter(i => i.s < 1).map(i => ({ dim: i.dim, id: i.id, s: Math.round(i.s * 100) / 100, why: i.why, hard: i.hard })), cards: nCards, chars: t.length };
}
