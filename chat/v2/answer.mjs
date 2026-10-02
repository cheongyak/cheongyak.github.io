// 검색 결과 → 답 (AI 없이 만드는 기본 답 + AI 설명에 넘길 사실 묶음).
// 답 모양 (사용자 예시 2026-10-02 '단지 비교' 답을 본뜸): 질문 받기 한 줄 → 이렇게 이해했어요 → 결론부터 → [후보별 핵심 지표] → [관점별로 보면] → [확인하지 못한 것] → [다음에 해볼 것].
// 지표 줄마다 상태(확인·추정·확인 불가)와 출처를 붙이고, 데이터가 없는 것(급지·호재·주차·학군)은 지어내지 않고 '청약패스에 데이터가 없어요'라고 쓴다.
import { fmtEok, signed, ELIG_WORD, SITE } from './search.mjs';
import { SP_LABEL, distKm as distKmA } from './lexicon.mjs';

// 화면과 같은 이름: 신혼희망타운은 '신혼희망타운', 무순위는 '무순위', 일반 물량 없는 주택형은 '특별공급 기준' (docs/index.html genLabel·verdict_one)
export const genWord = it => it.f.town ? '신혼희망타운' : it.f.category === 'remainder' ? '무순위' : it.genNone ? '특별공급 기준' : '일반공급';
const W = { required: '꼭', preferred: '되면 좋음', explore: '넓혀 보기' };
const d = s => s ? s.slice(5).replace('-', '.') : '';
const area = v => v == null ? '' : '전용 ' + (Math.round(v * 10) / 10) + '㎡';

export function understood(C) {
  const by = k => [...new Set(C.conds.filter(c => c.weight === k).map(c => [...new Set(String(c.text).split('·'))].join('·') + (c.explore_ok ? '(아니어도 됨)' : '')))];
  const a = C.assume || {}, as = [];
  if (a.married) as.push('신혼부부'); if (a.cash != null) as.push('현금 ' + fmtEok(a.cash)); if (a.income != null) as.push('연 소득 ' + a.income.toLocaleString('ko-KR') + '만원');
  if (a.homeless === true) as.push('무주택'); if (a.homeless === false) as.push('집 있음'); if (a.kids != null) as.push('자녀 ' + a.kids + '명');
  return { required: by('required'), preferred: by('preferred'), explore: by('explore'), assume: as, unsupported: C.unsupported || [], past: !!(C.scope && C.scope.past) };
}

// 이 후보를 보는 이유 한두 문장 — 위 지표에서만 뽑는다 (AI 설명이 살을 붙임)
function reasons(it, C) {
  const f = it.f, r = [];
  if (it.elig === 'ok') r.push(genWord(it) + ' 신청 가능' + ((it.sp || []).some(s => s.s === 'ok') ? '에 ' + it.sp.filter(s => s.s === 'ok').map(s => s.label).join('·') + ' 특별공급도 노려 볼 수 있어요' : '해요'));
  else if (it.elig === 'unsure') r.push(genWord(it) + ' 자격은 몇 가지 확인이 필요해요');
  if (f.margin.g === 'lotto' || f.margin.g === 'consider') r.push('주변 시세보다 ' + signed(f.margin.lo) + ' 이상 싸게 나온 편(추정)이에요');
  if (f.school.state === '추정' && f.school.walk <= 5) r.push('초등학교가 도보 ' + f.school.walk + '분(직선)이라 아이 키우기에 좋아요');
  if (f.station.state === '추정' && f.station.walk <= 7) r.push(f.station.name + ' 도보 ' + f.station.walk + '분(직선) 역세권이에요');
  if (f.complex.state === '확인' && f.complex.households >= 1000) r.push(f.complex.households.toLocaleString('ko-KR') + '세대 대단지예요');
  const cm = C ? C.conds.filter(c => c.key === 'commute') : [];
  if (cm.length && f.geo) { const near = cm.map(c => [c, distKmA(f.geo, c.value)]).sort((a, b) => a[1] - b[1])[0]; if (near[1] <= 8) r.push((near[0].value.who ? near[0].value.who + ' ' : '') + '직장과 가까워요(직선 약 ' + Math.round(near[1]) + 'km)'); }
  if (!f.past && f.dates.applyEnd && f.status === '접수 중' && f.dates.applyEnd <= (C && C.today || '')) r.push('오늘 접수가 끝나요');
  return r.length ? '→ ' + r.slice(0, 3).join(', ') + '.' : null;
}

function statusLine(f) {
  if (f.past) return '마감된 과거 공고 · 공고 ' + d(f.dates.notice) + ' (청약홈)';
  const sp = f.dates.special ? '특공 ' + d(f.dates.special) + ' · ' : '';
  return f.status + ' · ' + sp + '접수 ' + d(f.dates.apply) + (f.dates.applyEnd && f.dates.applyEnd !== f.dates.apply ? '~' + d(f.dates.applyEnd) : '') + (f.dates.winner ? ' · 발표 ' + d(f.dates.winner) : '') + ' (청약홈)';
}
export function card(it, { profile, C = null }) {
  const f = it.f, L = [];
  const cx = f.complex.state === '확인' ? '단지 ' + f.complex.households.toLocaleString('ko-KR') + '세대·' + f.complex.buildings + '개동' + (f.complex.single === 'maybe' ? '·나홀로 가능성' : '') : '단지 규모 확인 불가';
  L.push(`${f.name} (${[f.sido, f.district].filter(Boolean).join(' ')} · ${area(f.area.v)}(${f.unit}) · ${cx})`);
  const why = reasons(it, C);
  if (why) L.push(why);
  L.push('· 일정  ' + statusLine(f));
  L.push('· ' + f.price.label + '  ' + fmtEok(f.price.v) + ' (청약홈)');
  if (!f.rental) L.push('· 시세 차익  ' + (f.margin.g === 'unknown' ? '확인 불가 (주변 거래 부족)' : signed(f.margin.lo) + '~' + signed(f.margin.hi) + ' · ' + f.margin.name + ' (추정, 근거 거래 ' + f.margin.count + '건)'));
  if (f.jeonse.state === '추정') L.push('· 전세  약 ' + fmtEok(f.jeonse.v) + ' (추정, 입주장 할인 반영)');
  if (it.elig) L.push('· 내 자격  ' + (f.past ? '그때 넣었다면 ' : '') + genWord(it) + ' ' + ELIG_WORD[it.elig] + ((it.sp || []).length ? ' · 특공 ' + (it.sp.filter(s => s.s === 'ok').map(s => s.label).join('·') || '가능 없음') + (it.sp.some(s => s.s === 'ok') ? ' 가능' : '') : '') + ' (청약패스 판정)');
  else if (!profile) L.push('· 내 자격  내 조건을 넣으면 판정해요');
  else if (it.row && it.row.noJudge) L.push('· 내 자격  지난 공고 개요만 있어 판정하지 않아요');
  L.push('· 역  ' + (f.station.state === '추정' ? f.station.name + ' 도보 약 ' + f.station.walk + '분(직선 ' + f.station.m + 'm, 추정)' : '확인 불가' + (f.station.why ? ' (' + f.station.why + ')' : '')));
  L.push('· 초등학교  ' + (f.school.state === '추정' ? f.school.name + ' 도보 약 ' + f.school.walk + '분(직선 ' + f.school.m + 'm, 추정)' : '확인 불가' + (f.school.why ? ' (' + f.school.why + ')' : '')));
  const cm = C ? C.conds.filter(c => c.key === 'commute') : [];
  if (cm.length) L.push('· 출퇴근  ' + (f.geo ? cm.map(c => (c.value.who ? c.value.who + ' ' : '') + c.value.place.replace(/ \(중심 근사\)/, '') + '까지 직선 약 ' + Math.round(distKmA(f.geo, c.value)) + 'km').join(' · ') + ' (시간은 경로 조회 연결 뒤)' : '확인 불가 (단지 좌표 없음)'));
  if (f.competition) L.push('· 경쟁률  ' + f.competition.rows.slice(0, 2).map(r => r.rank + '순위 ' + r.reside + ' ' + r.rate + ':1').join(' · ') + ' (청약홈)');
  if (it.unknown && it.unknown.length) L.push('· 확인 필요  ' + [...new Set(it.unknown)].join(', '));
  L.push(f.link);
  return L.join('\n');
}

function conclusion(r, C, U) {
  const top = r.groups[0], nG = r.groups.length;
  if (!top) return null;
  const why = [];
  if (top.best.elig) why.push(genWord(top.best) + ' ' + ELIG_WORD[top.best.elig]);
  if (top.best.f.margin.g !== 'unknown' && !top.best.f.rental) why.push('시세 차익 ' + top.best.f.margin.name + '(추정)');
  if (top.best.f.status && !top.best.f.past) why.push(top.best.f.status);
  return `결론부터 말씀드리면, 조건에 맞는 곳은 ${nG}곳(주택형 ${r.ok.length}개)이고 가장 먼저 볼 곳은 ${top.name} ${top.best.f.unit}이에요${why.length ? ' — ' + why.join(' · ') : ''}.`;
}

export function compose(C, r, { profile = false, updated = '', mode = 'search', compare = null } = {}) {
  const U = understood(C), out = [];
  out.push(opening(C, r, mode));
  out.push('[이렇게 이해했어요]\n' + [U.required.length && '· 꼭: ' + U.required.join(', '), U.preferred.length && '· 되면 좋음: ' + U.preferred.join(', '), U.explore.length && '· 넓혀 보기: ' + U.explore.join(', '),
    U.assume.length && '· 이번 질문만의 가정: ' + U.assume.join(', ') + ' (저장된 내 조건은 바꾸지 않아요)', U.past && '· 지난 공고까지 포함'].filter(Boolean).join('\n') || '· 조건 없이 지금 접수 중·예정인 공고 전체');
  if (mode === 'compare' && compare) out.push(...compareBlocks(compare, { profile }));
  else if (r.ok.length) {
    out.push(conclusion(r, C, U));
    out.push('[후보별 핵심 지표]\n\n' + r.groups.slice(0, r.limit).map(g => card(g.best, { profile, C }) + (g.types.length > 1 ? '\n(같은 공고 다른 주택형 ' + (g.types.length - 1) + '개: ' + g.types.slice(1, 6).map(t => t.f.unit + ' ' + fmtEok(t.f.price.v)).join(' · ') + (g.types.length > 6 ? ' …' : '') + ')' : '')).join('\n\n'));
    if (r.nearMiss && r.nearMiss.length) out.push('[함께 눈여겨볼 곳 · 예산을 조금 넘어요]\n' + r.nearMiss.map(g => '· ' + g.name + ' ' + g.best.f.unit + ' — 분양가 ' + fmtEok(g.best.f.price.v) + (g.best.elig ? ', ' + genWord(g.best) + ' ' + ELIG_WORD[g.best.elig] : '') + (g.best.f.margin.g !== 'unknown' ? ', 시세 차익 ' + g.best.f.margin.name + '(추정)' : '') + '. 관심 단지로만 체크해 두세요.\n  ' + g.best.f.link).join('\n'));
    out.push(scenarios(r));
  } else {
    out.push(noResult(C, r, U));
  }
  if (r.unsure && r.unsure.length) {
    const g = groupBy(r.unsure);
    out.push('[확인이 필요한 후보 ' + g.length + '곳]\n' + g.slice(0, 4).map(x => '· ' + x[0].f.name + ' ' + x[0].f.unit + ' — ' + [...new Set(x[0].unknown)].join(', ') + (x[0].elig ? ' · ' + genWord(x[0]) + ' ' + ELIG_WORD[x[0].elig] : '') + '\n  ' + x[0].f.link).join('\n'));
  }
  if (r.refused && r.refused.length) out.push('[참고: 조건에는 맞지만 내 자격으로는 어려운 곳 ' + groupBy(r.refused).length + '곳] ' + groupBy(r.refused).slice(0, 3).map(x => x[0].f.name).join(', '));
  const miss = missing(C, r);
  if (miss.length) out.push('[확인하지 못한 것]\n' + miss.map(m => '· ' + m).join('\n'));
  out.push('[다음에 해볼 것]\n' + nextSteps(C, r, profile).map(s => '· ' + s).join('\n'));
  out.push('판정은 청약패스 화면과 같은 엔진으로, ' + (updated ? updated + ' 수집 데이터' : '오늘 데이터') + ' 기준이에요. 시세·거리는 추정이고, 신청 전에 모집공고문을 꼭 확인하세요.');
  return out.filter(Boolean).join('\n\n');
}

// 질문 받기: 질문자의 상황(아이·맞벌이 출퇴근·예산)을 한 번 되짚고, 무엇을 기준으로 따졌는지 말한다 (사용자 예시 2026-10-02)
function opening(C, r, mode) {
  if (mode === 'compare') return '좁혀 오신 단지들을 같은 기준으로 나란히 놓고 볼게요.';
  const a = C.assume || {}, who = C.conds.filter(c => c.key === 'commute' && c.value.who).map(c => c.value.who + ' ' + c.value.place.replace(/ \(중심 근사\)/, '').replace(/구$/, ''));
  const life = [a.kids ? '아이' + (a.youngest ? '(' + a.youngest + ')' : '') + '를 키우시면서' : '', who.length >= 2 ? '두 분 출퇴근(' + who.join(', ') + ')까지 챙기셔야 하니' : who.length ? who[0] + ' 출퇴근을 챙기셔야 하니' : ''].filter(Boolean);
  const price = C.conds.find(c => /^price/.test(c.key));
  const head = life.length ? life.join(' ') + ' 고민이 깊으셨을 것 같아요.' : C.conds.length >= 4 ? '조건을 꼼꼼하게 주셨네요.' : '';
  const basis = [C.conds.some(c => /^region/.test(c.key)) && '지역', price && '예산(' + price.text.replace(/\(.*\)/, '') + ')', C.conds.some(c => c.key === 'commute') && '출퇴근 거리', a.kids && '아이 키우기(초등학교 거리)', r.profile && '내 자격'].filter(Boolean);
  return (head ? head + '\n' : '') + basis.join(', ') + ' 기준으로 지금 청약패스에 있는 공고를 따져 봤어요.';
}
// 관점별 '이런 분께' — 사용자 예시의 '방장의 솔직한 생각'처럼 우선순위마다 다른 답을 준다 (판정·숫자는 위 지표 그대로)
function scenarios(r) {
  const P = r.perspectives || [], out = [];
  const say = { '가격 우선': '예산 여유를 가장 크게 남기고 싶다면', '시세 차익 우선(추정)': '당첨 뒤 시세 차익(추정)을 가장 크게 보고 싶다면', '당첨 길 우선': '당첨될 길이 많은 곳부터 넣고 싶다면' };
  const seen = new Set();
  for (const p of P) { const k = p.name + p.unit; if (seen.has(k) && out.length) continue; seen.add(k); out.push((say[p.label] || p.label.replace(/ 가까운 순$/, '') + '까지 가까운 곳을 원하시면') + ' ' + p.name + ' ' + p.unit + '을 먼저 보세요 — ' + p.why + '.'); }
  return out.length > 1 ? '[이런 분께는 이곳]\n' + out.map(x => '· ' + x).join('\n') : null;
}
const groupBy = items => { const m = new Map(); items.forEach(x => { const k = x.f.nid; if (!m.has(k)) m.set(k, []); m.get(k).push(x); }); return [...m.values()]; };

function noResult(C, r, U) {
  const parts = [];
  const all = [...U.required].join(' · ');
  parts.push(`${all ? all + ' 조건을 모두 만족하는 ' : ''}${C.scope && C.scope.past ? '' : '지금 접수 중·예정인 '}청약은 없어요.`);
  const ex = Object.entries(r.excluded).sort((a, b) => b[1] - a[1]);
  if (ex.length) parts.push('왜 없는지: 지금 ' + (C.scope && C.scope.past ? '' : '접수 중·예정 ') + '주택형 ' + r.total + '개 중 ' + ex.map(([k, n]) => k + ' ' + n + '개').join(', ') + '가 빠졌어요.');
  if (r.relax.length) parts.push('조건을 이렇게 바꾸면 생겨요:\n' + r.relax.map(o => '  [' + o.label + ' (' + o.count + '곳)]').join('\n'));
  const alt = r.relax.find(o => /인접 지역/.test(o.label)) || r.relax.find(o => !/지난 공고/.test(o.label));
  if (alt && alt.groups && alt.groups.length) parts.push('[대신 눈여겨볼 곳 · ' + alt.label + ']\n\n' + alt.groups.slice(0, 3).map(g => card(g.best, { profile: r.profile, C })).join('\n\n'));
  if (r.explore && r.explore.nearby.length) parts.push('가까운 지역에는 지금 공고가 있어요 (좌표 거리 기준): ' + r.explore.nearby.map(x => x.label + ' ' + x.count + '개(' + x.of + '에서 약 ' + x.km + 'km)').join(', '));
  parts.push('기다리신다면 [이 조건으로 새 공고 알림 받기]로 공고가 올라오는 날 알려 드릴게요.');
  return parts.join('\n');
}

function missing(C, r) {
  const m = [...(C.unsupported || []).map(u => u + ' — 청약패스에 이 데이터가 없어 답하지 않았어요')];
  if (C.conds.some(c => c.key === 'rooms')) m.push('방·욕실 수 — 아직 공고문에서 모으지 않아, 해당 후보는 \'구조 확인 필요\'로 따로 뒀어요');
  for (const c of C.conds.filter(c => c.key === 'commute')) m.push(c.value.place + ' 출퇴근 시간 — 경로 조회를 아직 연결하지 않아, 직선거리로만 순서를 봤어요(시간으로 바꾸지 않음)');
  if (C.conds.some(c => c.key === 'eligible_only') && !r.profile) m.push('내 자격 — 내 조건을 넣지 않아 판정하지 못했어요');
  return m;
}

function nextSteps(C, r, profile) {
  const s = [], a = C.assume || {};
  if (a.kids && !profile) s.push('막내 생일을 알려 주시면 신생아 특별공급(공고일 기준 2세 미만 자녀)·신혼부부 특별공급까지 판정해 드려요');
  if (!C.conds.some(c => c.key === 'area')) s.push('20평대(전용 59㎡)와 30평대(전용 84㎡) 중 어느 쪽에 마음이 기우시는지 알려 주시면 더 좁혀 드릴게요');
  if (!profile) s.push('[내 조건 넣기] 그러면 후보마다 일반공급·특별공급 자격을 판정해 드려요');
  if (r.ok.length > 1) s.push('[' + (r.groups[0] && r.groups[1] ? r.groups[0].name + ' vs ' + r.groups[1].name + ' 비교' : '두 곳 비교') + ']');
  if (r.ok.length) s.push('[시세 차익 큰 순으로] [가격 낮은 순으로]');
  if (!C.scope || !C.scope.past) s.push('[이 지역 지난 공고 경쟁률 보기]');
  s.push('[이 조건으로 새 공고 알림 받기]');
  return s;
}

// ---- 비교 ----
export function buildCompare(D, targets, C, { profile = null } = {}) {
  const p = profile ? D.profileOf(profile) : null, big = /(큰 평수|가장 큰|대형|넓은)/.test(C.q || '');
  return targets.map(t => {
    if (!t.found) return { query: t.query, found: false };
    const byN = new Map(); t.rows.forEach(r => { const k = r.L.id.split('-')[0]; if (!byN.has(k)) byN.set(k, []); byN.get(k).push(r); });
    return { query: t.query, found: true, notices: [...byN.values()].map(rows => {
      const pick = rows.slice().sort((a, b) => big ? (b.L.area - a.L.area) : Math.abs(a.L.area - 84) - Math.abs(b.L.area - 84))[0];
      const it = { row: pick, f: null, unknown: [] };
      return { rows, pick: it, all: rows.map(r => ({ unit: String(r.L.unitName || r.L.unit).trim(), price: r.L.price, area: r.L.area })), p, big };
    }) };
  });
}
function compareBlocks(cmp, { profile }) {
  const out = [], blocks = [];
  for (const t of cmp) {
    if (!t.found) { blocks.push(`'${t.query}' — 청약패스 공고(지금·지난 1년)에서 찾지 못했어요. 청약패스는 새 분양 공고만 다뤄서, 이미 지어진 아파트 매매 비교는 아직 못 해요.`); continue; }
    for (const n of t.notices) blocks.push(card(n.pick, { profile }) + (n.all.length > 1 ? '\n(주택형 ' + n.all.length + '개: ' + n.all.sort((a, b) => a.area - b.area).map(a => a.unit + ' ' + fmtEok(a.price)).join(' · ') + ')' : ''));
  }
  const found = cmp.filter(t => t.found).flatMap(t => t.notices.map(n => n.pick));
  if (found.length >= 2) {
    const bestM = found.slice().sort((a, b) => (b.f.margin.lo ?? -99) - (a.f.margin.lo ?? -99))[0], cheap = found.slice().sort((a, b) => a.f.price.v - b.f.price.v)[0];
    out.push('결론부터 말씀드리면, 시세 차익(추정)은 ' + bestM.f.name + ' ' + bestM.f.unit + '이 가장 크고, 분양가는 ' + cheap.f.name + ' ' + cheap.f.unit + '이 가장 낮아요.' + (found.some(x => x.elig) ? ' 내 자격은 아래 지표의 \'내 자격\' 줄을 보세요.' : ''));
  }
  out.push('[단지별 핵심 지표' + (cmp.some(t => t.found && t.notices.some(n => n.big)) ? ' · 가장 큰 주택형 기준' : ' · 84㎡에 가까운 주택형 기준') + ']\n\n' + blocks.join('\n\n'));
  return out;
}
