// 검색 결과 → 답 (AI 없이 만드는 기본 답 + AI 설명에 넘길 사실 묶음).
// 답 모양 (사용자 예시 2026-10-02 '단지 비교' 답을 본뜸): 질문 받기 한 줄 → 이렇게 이해했어요 → 결론부터 → [후보별 핵심 지표] → [관점별로 보면] → [확인하지 못한 것] → [다음에 해볼 것].
// 지표 줄마다 상태(확인·추정·확인 불가)와 출처를 붙이고, 데이터가 없는 것(급지·호재·주차·학군)은 지어내지 않고 '청약패스에 데이터가 없어요'라고 쓴다.
import { fmtEok, signed, ELIG_WORD, SITE } from './search.mjs';
import { SP_LABEL, REGION_SETS, distKm as distKmA } from './lexicon.mjs';

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
  if (a.family) as.push(a.family + '인 가족'); if (a.no_school) as.push('학군은 안 따짐');
  return { required: by('required'), preferred: by('preferred'), explore: by('explore'), assume: as, unsupported: C.unsupported || [], past: !!(C.scope && C.scope.past) };
}

// 이 후보를 보는 이유 한두 문장 — 위 지표에서만 뽑는다 (AI 설명이 살을 붙임)
function reasons(it, C) {
  const f = it.f, r = [];
  if (it.elig === 'ok') r.push(genWord(it) + ' 신청 가능' + ((it.sp || []).some(s => s.s === 'ok') ? '에 ' + it.sp.filter(s => s.s === 'ok').map(s => s.label).join('·') + ' 특별공급도 노려 볼 수 있어요' : '해요'));
  else if (it.elig === 'unsure') r.push(genWord(it) + ' 자격은 몇 가지 확인이 필요해요');
  if (f.margin.g === 'lotto' || f.margin.g === 'consider') r.push('주변 시세보다 ' + signed(f.margin.lo) + ' 이상 싸게 나온 편(추정)이에요');
  const noSchool = C && (C.assume || {}).no_school;   // '학군지 필요없어' — 학교를 장점으로 내세우지 않는다 (샘플 3)
  if (!noSchool && f.school.state === '추정' && f.school.walk <= 5) r.push('초등학교가 가까워요' + (C && ((C.assume || {}).kids || C.conds.some(c => c.key === 'school_walk')) ? ' 아이 키우기에 좋아요' : ''));
  const wantsTransit = C && C.conds.some(c => c.key === 'station_walk'), wantsLive = C && (C.perspectives || []).includes('livability');
  if (f.station.state === '추정' && f.station.walk <= (wantsTransit ? 10 : 7)) r.push(f.station.name + ' 도보 약 ' + f.station.walk + '분이라 ' + (wantsTransit ? '교통이 편해요' : '역세권이에요'));
  if (f.complex.state === '확인' && f.complex.households >= (wantsLive ? 500 : 1000)) r.push(f.complex.households.toLocaleString('ko-KR') + '세대 ' + (f.complex.households >= 1000 ? '대단지' : '단지') + (wantsLive ? '라 생활 편의시설을 기대할 만해요' : '예요'));
  const cm = C ? C.conds.filter(c => c.key === 'commute') : [];
  if (cm.length && f.geo) { const near = cm.map(c => [c, distKmA(f.geo, c.value)]).sort((a, b) => a[1] - b[1])[0]; if (near[1] <= 8) r.push((near[0].value.who ? near[0].value.who + ' ' : '') + '직장과 가까워요(직선 약 ' + Math.round(near[1]) + 'km)'); }
  if (!f.past && f.dates.applyEnd && f.status === '접수 중' && f.dates.applyEnd <= (C && C.today || '')) r.push('오늘 접수가 끝나요');
  if (r.length < 2 && C) {   // 눈에 띄는 점이 없으면 질문 조건과 이어지는 사실 하나 (예산 여유·면적)
    const pm = C.conds.find(c => c.key === 'price_max');
    if (pm && f.price.v != null && pm.value - f.price.v >= 0.3) r.push('예산(' + pm.value + '억)보다 ' + fmtEok(Math.round((pm.value - f.price.v) * 100) / 100) + ' 여유 있어요');
    else if (f.complex.state === '확인' && f.complex.single === 'no' && f.complex.households >= 500) r.push(f.complex.households.toLocaleString('ko-KR') + '세대 단지예요');
    else if (f.units.general + f.units.special > 0 && !r.length) r.push('이 주택형 공급 ' + (f.units.general + f.units.special) + '세대(일반 ' + f.units.general + '·특공 ' + f.units.special + ')예요');
  }
  return r.length ? '→ ' + r.slice(0, 3).join(', ') + '.' : null;
}

// 특공 요약: '가능 없음'처럼 물어본 유형 줄과 엇갈려 보이는 말 대신 가능·확인 필요·불가를 나눠 쓴다 (AI 심사 회차 1)
const spLine = sp => { const by = k => sp.filter(s => s.s === k).map(s => s.label); const ok = by('ok'), w = by('warn');
  return ' · 특공 ' + [ok.length && '가능 ' + ok.join('·'), w.length && '확인 필요 ' + w.join('·'), !ok.length && !w.length && '모두 어려움'].filter(Boolean).join(' / '); };
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
  if (!f.rental) L.push('· 시세 차익  ' + (f.margin.g === 'unknown' ? '확인 불가 (주변 거래 부족)' : signed(f.margin.lo) + '~' + signed(f.margin.hi) + ' · ' + f.margin.name + ' (추정, 근거 거래 ' + f.margin.count + '건' + (f.margin.count < 5 ? ' — 거래가 적어 참고만' : '') + ')'));   // 근거가 얇으면 바로 옆에 (샘플 3 '중개사 1곳 — 확인 필요')
  if (f.jeonse.state === '추정') L.push('· 전세  약 ' + fmtEok(f.jeonse.v) + ' (추정, 입주장 할인 반영)');
  const askSp = C ? C.conds.filter(c => c.key === 'supply' && /^sp:/.test(c.value)).map(c => c.value.slice(3)) : [];
  for (const t of askSp) { const x = (it.sp || []).find(s => s.type === t); L.push('· ' + SP_LABEL[t] + ' 특공  ' + (!it.elig && !x ? '내 조건을 넣으면 판정해요' : x ? { ok: '신청 가능', warn: '확인 필요', fail: '신청 불가' }[x.s] + ' (청약패스 판정)' : '이 주택형에는 없어요')); }   // 물어본 특공 유형은 따로 한 줄 (회차 1: '생애최초'를 물었는데 '특공 가능 없음'만)
  if (it.elig) L.push('· 내 자격  ' + (f.past ? '그때 넣었다면 ' : '') + genWord(it) + ' ' + ELIG_WORD[it.elig] + ((it.sp || []).length ? spLine(it.sp)  : '') + ' (청약패스 판정)');
  else if (!profile) L.push('· 내 자격  내 조건을 넣으면 판정해요');
  else if (it.row && it.row.noJudge) L.push('· 내 자격  지난 공고 개요만 있어 판정하지 않아요');
  for (const c of (C ? C.conds.filter(c => c.key === 'line') : [])) { const n = f.line && f.line[c.value.line];   // 노선 조건이면 그 노선 가장 가까운 역 (샘플 4)
    L.push('· ' + c.value.line + '  ' + (n ? n.name + '역 직선 ' + (n.m >= 1000 ? (Math.round(n.m / 100) / 10) + 'km' : n.m + 'm') + ' (역 위치 OpenStreetMap, 추정)' : '확인 불가 (단지 좌표 또는 역 정보 없음)')); }
  L.push('· 역  ' + (f.station.state === '추정' ? f.station.name + ' 도보 약 ' + f.station.walk + '분(직선 ' + f.station.m + 'm, 추정)' : '확인 불가' + (f.station.why ? ' (' + f.station.why + ')' : '')));
  if (!(C && (C.assume || {}).no_school)) L.push('· 초등학교  ' + (f.school.state === '추정' ? f.school.name + ' 도보 약 ' + f.school.walk + '분(직선 ' + f.school.m + 'm, 추정)' : '확인 불가' + (f.school.why ? ' (' + f.school.why + ')' : '')));
  const cm = C ? C.conds.filter(c => c.key === 'commute') : [];
  if (cm.length) L.push('· 출퇴근  ' + (!f.geo ? '확인 불가 (단지 좌표 없음)' : cm.map(c => { const nm = (c.value.who ? c.value.who + ' ' : '') + c.value.place.replace(/ \(중심 근사\)/, '');
    const t = (f.commute || []).find(x => x.place === c.value.place && x.who === (c.value.who || ''));
    return t && t.min != null ? nm + '까지 자동차 약 ' + t.min + '분(' + t.km + 'km, ' + t.src.replace(/ \(.*\)$/, '') + ' ' + t.at.slice(11, 16).replace(/^(\d\d)/, h => String((+h + 9) % 24).padStart(2, '0')) + ' 조회)' : nm + '까지 직선 약 ' + Math.round(distKmA(f.geo, c.value)) + 'km(시간 확인 불가)'; }).join(' · ') + (f.geo && !f.geo.precise ? ' — 단지 좌표가 동 단위라 대략이에요' : '')));
  if (f.competition) L.push('· 경쟁률  ' + f.competition.rows.slice(0, 2).map(r => r.rank + '순위 ' + r.reside + ' ' + r.rate + ':1').join(' · ') + ' (청약홈)');
  if (it.unknown && it.unknown.length) L.push('· 확인 필요  ' + [...new Set(it.unknown)].join(', '));
  const miss = (it.pref || []).filter(x => x.s === 'fail' && x.key !== 'region_in' && x.key !== 'margin').map(x => x.why);
  if (miss.length) L.push('· 아쉬운 점  ' + miss.join(', '));   // 원하신 조건 중 안 맞는 것 (회차 1: 초품아 위주인데 안 맞는 곳을 말하지 않음)
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
  return `결론부터 말씀드리면, 조건에 맞는 곳은 ${nG}곳(주택형 ${r.ok.length}개)${nG > (r.limit || 3) ? '이고, 그중 먼저 볼 ' + (r.limit || 3) + '곳을 골랐어요. 1순위는' : '이고 가장 먼저 볼 곳은'} ${top.name} ${top.best.f.unit}이에요${why.length ? ' — ' + why.join(' · ') : ''}.`;
}

export function compose(C, r0, { profile = false, updated = '', mode = 'search', compare = null } = {}) {
  let r = r0;
  const U = understood(C), out = [];
  out.push(opening(C, r, mode));
  out.push('[이렇게 이해했어요]\n' + [U.required.length && '· 꼭: ' + U.required.join(', '), U.preferred.length && '· 되면 좋음: ' + U.preferred.join(', '), U.explore.length && '· 넓혀 보기: ' + U.explore.join(', '),
    U.assume.length && '· 이번 질문만의 가정: ' + U.assume.join(', ') + ' (저장된 내 조건은 바꾸지 않아요)', U.past && '· 지난 공고까지 포함', ...Object.keys(REGION_SETS).filter(k => C.conds.some(c => c.key === 'region_in' && c.value.some(v => v.label === k))).map(k => '· ' + k + '는 이렇게 봤어요: ' + REGION_SETS[k].map(x => x.replace(/(시|군)$/, '')).join('·') + ' (한강 ' + (k === '경기남부' ? '남쪽' : '북쪽') + ' 경기 시·군)'), U.unsupported.some(u => /^층 고르기/.test(u)) && '· 따를 수 없는 것: 저층 제외 — 청약은 당첨 뒤 동·호수를 추첨으로 정해요', mode === 'compare' && '· 비교할 단지: ' + (C.targets || []).join(', ') + (/(큰 평수|가장 큰|대형|넓은)/.test(C.q || '') ? ' (가장 큰 주택형 기준)' : ''), U.unsupported.length && mode === 'compare' && '· 데이터가 없어 답하지 않는 것: ' + U.unsupported.join(', '), (C.perspectives || []).length && '· 중요하게 보는 것: ' + C.perspectives.map(p => ({ margin: '시세 차익', chance: '당첨 가능성', price: '가격', growth: '가격 상승력(시세 차익으로 봄)', livability: '실거주 만족도' }[p] || p)).join(', ')].filter(Boolean).join('\n') || '· 조건 없이 지금 접수 중·예정인 공고 전체');
  for (const li of (r.lineInfo || [])) out.push(li.missing ? '· ' + li.line + ' 역 위치 자료가 아직 없어 노선 조건은 확인하지 못했어요.' : '[' + li.line + ' 역세권 공고 현황]\n' + (li.notices ? '지금 접수 중·예정인 공고 중 ' + li.line + ' 역까지 직선 ' + (li.m / 1000) + 'km 안은 ' + li.notices + '곳(주택형 ' + li.types + '개, ' + li.stations.join('·') + '역 주변)이고, 가장 싼 주택형이 ' + fmtEok(li.minPrice) + '이에요.' : '지금 접수 중·예정인 공고 중 ' + li.line + ' 역까지 직선 ' + (li.m / 1000) + 'km 안에 있는 곳은 없어요. 새 공고가 이 노선에 뜨면 알려 드릴게요.'));
  if (mode === 'compare' && compare) out.push(...compareBlocks(compare, { profile }));
  else if (r.ok.length) {
    out.push(conclusion(r, C, U));
    out.push('[후보별 핵심 지표' + (r.groups.length > r.limit ? ' · ' + r.groups.length + '곳 중 먼저 볼 ' + r.limit + '곳' : '') + ']\n\n' + r.groups.slice(0, r.limit).map(g => card(g.best, { profile, C }) + (g.types.length > 1 ? '\n(같은 공고 다른 주택형 ' + (g.types.length - 1) + '개: ' + g.types.slice(1, 6).map(t => t.f.unit + ' ' + fmtEok(t.f.price.v)).join(' · ') + (g.types.length > 6 ? ' …' : '') + ')' : '')).join('\n\n'));
    if (r.groups.length > r.limit) out.push('[나머지 ' + (r.groups.length - r.limit) + '곳]\n' + r.groups.slice(r.limit).map(g => '· ' + g.name + ' ' + g.best.f.unit + ' — ' + g.best.f.price.label + ' ' + fmtEok(g.best.f.price.v) + (g.best.elig ? ' · ' + genWord(g.best) + ' ' + ELIG_WORD[g.best.elig] : '') + (g.best.far ? ' · 직장에서 멀어요' : '') + '\n  ' + g.best.f.link).join('\n'));
    if (r.nearMiss && r.nearMiss.length) out.push('[함께 눈여겨볼 곳 · 예산을 조금 넘어요]\n' + r.nearMiss.map(g => '· ' + g.name + ' ' + g.best.f.unit + ' — 분양가 ' + fmtEok(g.best.f.price.v) + (g.best.elig ? ', ' + genWord(g.best) + ' ' + ELIG_WORD[g.best.elig] : '') + (g.best.f.margin.g !== 'unknown' ? ', 시세 차익 ' + g.best.f.margin.name + '(추정)' : '') + '. 관심 단지로만 체크해 두세요.\n  ' + g.best.f.link).join('\n'));
    out.push(scenarios(r));
    if (r.outside && r.outside.groups.length) out.push(outsideBlock(r, C, profile));
  } else if (r.outside && r.outside.groups.length && !(r.unsure && r.unsure.length)) {   // 그 지역엔 없고 다른 지역에는 같은 조건이 있다 — '없어요'로 끝내지 않고 넓힌 결과를 본론으로
    const o = r.outside, top = o.groups[0];
    out.push(`결론부터 말씀드리면, ${o.base.join('·')} 안에는 지금 이 조건(${[...U.required].filter(x => !o.base.includes(x)).join(' · ')})에 맞는 접수 중·예정 청약이 없어요. 같은 조건으로 ${o.base.join('·')} 밖까지 넓히면 ${o.total}곳이 있고, 먼저 볼 곳은 ${top.name} ${top.best.f.unit}이에요${top.best.km != null ? '(' + o.base.join('·') + '에서 직선 약 ' + top.best.km + 'km)' : ''}.`);
    out.push(outsideBlock(r, C, profile));
    if (r.relax && r.relax.length) out.push('조건을 이렇게 바꿔도 볼 수 있어요:\n' + r.relax.filter(x => !/인접 지역/.test(x.label)).map(o => '  [' + o.label + ' (' + o.count + '곳)]').join('\n'));
  } else {
    if (r.unsure && r.unsure.length) {   // 조건 일부를 데이터로 확인 못 해 '확인 필요'로 남은 곳만 있다 — '없다'고 하지 않는다 (2026-10-03 품질 검사: 방3화2 질문에 '청약은 없어요')
      const g = groupBy(r.unsure), why = [...new Set(r.unsure.flatMap(x => x.unknown.map(u => u.replace(/\s?확인 (필요|불가)$/, ''))))];
      const how = why.some(w => /방|욕실|구조/.test(w)) ? '청약패스에 그 데이터가 아직 없어서 모집공고문 평면도·공급표로 확인해 주세요.' : '청약패스에 그 데이터가 아직 없어 확인하지 못했어요.';   // 이유에 맞는 안내 (샘플 4 점검: 노선 정보 없음에도 평면도 안내가 나왔음)
      out.push(`결론부터 말씀드리면, 확실히 맞는 곳은 아직 없지만 ${why.join(', ')}만 확인하면 되는 곳이 ${g.length}곳(주택형 ${r.unsure.length}개) 있어요. ${how}`);
      out.push('[확인하면 되는 후보]\n\n' + g.slice(0, r.limit || 5).map(x => card(x[0], { profile, C })).join('\n\n'));
      r = { ...r, unsure: [] };
    } else { const nr = noResult(C, r, U).split('\n'); out.push(nr[0]); out.push(nr.slice(1).join('\n')); }
  }
  if (mode === 'compare') { const miss = missing(C, r); if (miss.length) out.push('[확인하지 못한 것]\n' + miss.map(m => '· ' + m).join('\n'));
    out.push('[다음에 해볼 것]\n' + [compare && compare.some(t => t.found) ? '가격·시세 차익·당첨 가능성 중 무엇을 가장 중요하게 보시는지 알려 주시면 한 곳으로 좁혀 드릴게요' : '이 동네 이름으로 청약 공고를 찾아 드릴까요? 예산과 원하는 평수를 같이 알려 주시면 더 좁혀 드릴게요', compare && compare.some(t => t.found) ? '[두 곳 중 내 자격으로 특별공급까지 되는 곳만 보기]' : '[이 동네 지난 청약 공고 보기]', '[이 지역 지난 공고 경쟁률 보기]', '[이 조건으로 새 공고 알림 받기]'].map(x => '· ' + x).join('\n'));
    out.push('판정은 청약패스 화면과 같은 엔진으로, ' + (updated || '오늘') + ' 데이터 기준이에요. 시세·거리는 추정이고, 신청 전에 모집공고문을 꼭 확인하세요.');
    return reorder(out).filter(Boolean).join('\n\n'); }
  if (r.unsure && r.unsure.length) {
    const g = groupBy(r.unsure);
    out.push('[확인이 필요한 후보 ' + g.length + '곳]\n' + g.slice(0, 4).map(x => '· ' + x[0].f.name + ' ' + x[0].f.unit + ' — ' + [...new Set(x[0].unknown)].join(', ') + (x[0].elig ? ' · ' + genWord(x[0]) + ' ' + ELIG_WORD[x[0].elig] : '') + '\n  ' + x[0].f.link).join('\n'));
  }
  if (r.refused && r.refused.length) out.push('[참고: 조건에는 맞지만 내 자격으로는 어려운 곳 ' + groupBy(r.refused).length + '곳] ' + groupBy(r.refused).slice(0, 3).map(x => x[0].f.name).join(', '));
  const miss = missing(C, r);
  if (miss.length) out.push('[확인하지 못한 것]\n' + miss.map(m => '· ' + m).join('\n'));
  out.push('[다음에 해볼 것]\n' + nextSteps(C, r, profile).map(s => '· ' + s).join('\n'));
  out.push('판정은 청약패스 화면과 같은 엔진으로, ' + (updated ? updated + ' 수집 데이터' : '오늘 데이터') + ' 기준이에요. 시세·거리는 추정이고, 신청 전에 모집공고문을 꼭 확인하세요.');
  return reorder(out).filter(Boolean).join('\n\n');
}
// '마포구 말고도 같은 조건으로' — 그 지역 밖 후보 (지역만 풀고 다른 조건은 그대로). 왜 골랐는지: 거리 + 질문의 우선순위와 맞는 점 (샘플 3)
function outsideBlock(r, C, profile) {
  const o = r.outside;
  const head = '[' + o.base.join('·') + ' 밖 · 같은 조건' + (o.unsure ? ' (일부 확인 필요)' : '') + ']\n같은 예산·면적 조건으로 ' + o.base.join('·') + ' 밖에서 고른 곳이에요. 신청할 수 있는 곳, 말씀하신 우선순위에 맞는 곳, ' + o.base.join('·') + '에서 가까운 곳 순이에요.';
  return head + '\n\n' + o.groups.map(g => card(g.best, { profile, C }) + (g.best.km != null ? '\n왜 여기: ' + o.base.join('·') + '에서 직선 약 ' + g.best.km + 'km' : '')).join('\n\n') + (o.total > o.groups.length ? '\n\n(같은 조건으로 ' + (o.total - o.groups.length) + '곳 더 있어요 — [더 보기])' : '') + priorityPicks(o.groups.map(g => g.best), C);
}
// 우선순위별 '먼저 볼 곳' — 질문에서 말한 우선순위마다 위 지표에서 가장 나은 곳 (샘플 3 결론 '…을 최우선으로 보신다면 A, … 를 더 선호하신다면 B')
function priorityPicks(items, C) {
  if (items.length < 2) return '';
  const P = C.perspectives || [], lines = [];
  const pick = (fn, ok) => items.filter(ok).sort(fn)[0];
  if (P.includes('growth') || P.includes('margin')) { const x = pick((a, b) => (b.f.margin.lo ?? -99) - (a.f.margin.lo ?? -99), x => x.f.margin.g !== 'unknown'); if (x) lines.push('가격 상승력(시세 차익)을 가장 크게 보시면 ' + x.f.name + ' — 주변 시세보다 ' + signed(x.f.margin.lo) + '~' + signed(x.f.margin.hi) + ' (추정' + (x.f.margin.count < 5 ? ', 거래 ' + x.f.margin.count + '건이라 참고만' : '') + ')'); }
  if (C.conds.some(c => c.key === 'station_walk')) { const x = pick((a, b) => a.f.station.walk - b.f.station.walk, x => x.f.station.state === '추정'); if (x) lines.push('교통을 먼저 보시면 ' + x.f.name + ' — ' + x.f.station.name + ' 도보 약 ' + x.f.station.walk + '분'); }
  if (P.includes('livability')) { const x = pick((a, b) => b.f.complex.households - a.f.complex.households, x => x.f.complex.state === '확인'); if (x) lines.push('단지 규모·생활 편의를 먼저 보시면 ' + x.f.name + ' — ' + x.f.complex.households.toLocaleString('ko-KR') + '세대'); }
  const pr = C.conds.find(c => c.key === 'price_max');
  if (pr && lines.length < 3) { const x = pick((a, b) => a.f.price.v - b.f.price.v, x => x.f.price.v != null); if (x) lines.push('예산 여유를 가장 크게 남기시려면 ' + x.f.name + ' — 분양가 ' + fmtEok(x.f.price.v) + ', 예산보다 ' + fmtEok(Math.round((pr.value - x.f.price.v) * 100) / 100) + ' 여유'); }
  const uniq = [...new Set(lines)];
  return uniq.length >= 2 ? '\n\n[우선순위별로 먼저 볼 곳]\n' + uniq.map(x => '· ' + x).join('\n') : '';
}

// 결론을 '이렇게 이해했어요' 앞으로 (AI 심사 회차 2: '없어요'를 먼저 분명히 말한 뒤 이해한 조건·대안 순서가 낫다)
function reorder(out) {
  const u = out.findIndex(x => typeof x === 'string' && x.startsWith('[이렇게 이해했어요]')), c = out.findIndex(x => typeof x === 'string' && /^(결론부터 말씀드리면|.*청약은 없어요\.$)/.test(x));
  if (u >= 0 && c > u) { const [blk] = out.splice(u, 1); out.splice(c, 0, blk); }
  // 노선 현황은 결론 바로 뒤 (샘플 4: 결론 → 기준·권역 설명 순서)
  const li = out.map((x, i) => typeof x === 'string' && /^(\[.+ 역세권 공고 현황\]|· .+ 역 위치 자료가)/.test(x) ? i : -1).filter(i => i >= 0);
  if (li.length) { const blocks = li.map(i => out[i]); for (const i of li.slice().reverse()) out.splice(i, 1);
    const c2 = out.findIndex(x => typeof x === 'string' && /^(결론부터 말씀드리면|.*청약은 없어요\.$)/.test(x)); out.splice(c2 >= 0 ? c2 + 1 : 1, 0, ...blocks); }
  return out;
}

// 질문 받기: 질문자의 상황(아이·맞벌이 출퇴근·예산)을 한 번 되짚고, 무엇을 기준으로 따졌는지 말한다 (사용자 예시 2026-10-02)
function opening(C, r, mode) {
  if (mode === 'compare') return '좁혀 오신 단지들을 같은 기준으로 나란히 놓고 볼게요.';
  const a = C.assume || {}, who = C.conds.filter(c => c.key === 'commute' && c.value.who).map(c => c.value.who + ' ' + c.value.place.replace(/ \(중심 근사\)/, '').replace(/구$/, ''));
  const life = [a.kids ? '아이' + (a.youngest ? '(' + a.youngest + ')' : '') + '를 키우시면서' : '', who.length >= 2 ? '두 분 출퇴근(' + who.join(', ') + ')까지 챙기셔야 하니' : who.length ? who[0] + ' 출퇴근을 챙기셔야 하니' : ''].filter(Boolean);
  const price = C.conds.find(c => /^price/.test(c.key));
  // 질문자의 상황·우선순위를 한 문장으로 되짚는다 (샘플 3 '4인 가족이 함께 거주하면서 … 30평대를 찾고 계시네요')
  const reg = C.conds.filter(c => c.key === 'region_in' && c.weight === 'required').flatMap(c => c.value.map(v => v.label)), ar = C.conds.find(c => c.key === 'area');
  const pri = [(C.perspectives || []).includes('growth') && '가격 상승력', C.conds.some(c => c.key === 'station_walk') && '교통', (C.perspectives || []).includes('livability') && '실거주 만족도', C.conds.some(c => c.key === 'school_walk') && '아이 통학', (C.perspectives || []).includes('margin') && '시세 차익'].filter(Boolean);
  const sit = (a.family || reg.length || ar) && pri.length ? (a.family ? a.family + '인 가족이 ' : '') + (reg.length ? [...new Set(reg)].join('·') + '에서 ' : '') + (ar ? String(ar.text).replace(/\(.*\)/, '') + ' 집에 ' : '') + '실거주하시면서 ' + pri.join('·') + '까지 챙기고 싶으시군요.' : '';
  const head = life.length ? life.join(' ') + ' 고민이 깊으셨을 것 같아요.' : sit || (C.conds.length >= 4 ? '조건을 꼼꼼하게 주셨네요.' : '');
  const basis = [C.conds.some(c => /^region/.test(c.key)) && '지역', C.conds.some(c => c.key === 'rooms') && '방 구조', C.conds.some(c => c.key === 'area') && '면적', price && '예산(' + price.text.replace(/\(.*\)/, '') + ')', C.conds.some(c => c.key === 'commute') && '출퇴근 거리', a.kids && '아이 키우기(초등학교 거리)', r.profile && '내 자격'].filter(Boolean);
  const resale = (C.unsupported || []).some(u => /^기존 아파트 매매/.test(u));   // '매물도 추천해줘' — 왜 매매 추천이 없는지 처음에 (AI 회차 4 심사)
  return (head ? head + '\n' : '') + (basis.length ? basis.join(', ') + ' 기준으로' : '말씀하신 조건으로') + ' 지금 청약패스에 있는 공고를 따져 봤어요.'
    + (resale ? '\n말씀하신 매물(이미 지어진 아파트 매매)은 청약패스가 다루지 않아서, 같은 조건의 새 분양(청약) 공고로 찾아봤어요. 기존 아파트 실거래가는 국토교통부 실거래가 공개시스템(rt.molit.go.kr)에서 볼 수 있어요.' : '');
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
  if (ex.length) parts.push('왜 없는지: 지금 ' + (C.scope && C.scope.past || C.conds.some(c => c.key === 'status') ? '' : '접수 중·예정 ') + '주택형 ' + r.total + '개 중 ' + ex.map(([k, n]) => k + ' ' + n + '개').join(', ') + '가 빠졌어요.');
  if (r.relax.length) parts.push('조건을 이렇게 바꾸면 생겨요:\n' + r.relax.map(o => '  [' + o.label + ' (' + o.count + '곳)]').join('\n'));
  const alt = r.relax.find(o => /인접 지역/.test(o.label)) || r.relax.find(o => !/지난 공고/.test(o.label));
  if (!(alt && alt.groups && alt.groups.length) && r.closest && r.closest.length) parts.push('[조건에 가장 가까운 곳 · 조건 ' + r.closest[0].misses.length + '개만 아쉬워요]\n\n' + r.closest.map(x => card(x, { profile: r.profile, C }) + '\n아쉬운 점: ' + x.misses.join(', ') + (x.km != null ? ' · 말씀하신 지역에서 직선 약 ' + x.km + 'km' : '')).join('\n\n'));
  const regs = C.conds.filter(c => c.key === 'region_in').flatMap(c => c.value).filter(v => v.lat);
  const whyHere = it => { if (!regs.length || !it.f.geo) return ''; const d = Math.min(...regs.map(v => distKmA(it.f.geo, v))); return '\n왜 여기: 말씀하신 ' + regs.map(v => v.label).join('·') + '에서 직선 약 ' + Math.round(d) + 'km'; };   // 대안을 왜 골랐는지 (AI 심사 회차 3)
  if (alt && alt.groups && alt.groups.length) parts.push('[대신 눈여겨볼 곳 · ' + alt.label + ']\n\n' + alt.groups.slice(0, 3).map(g => card(g.best, { profile: r.profile, C }) + whyHere(g.best)).join('\n\n'));
  if (r.explore && r.explore.nearby.length) parts.push('가까운 지역에는 지금 공고가 있어요 (좌표 거리 기준): ' + r.explore.nearby.map(x => x.label + ' ' + x.count + '개(' + x.of + '에서 약 ' + x.km + 'km)').join(', '));
  parts.push('기다리신다면 [이 조건으로 새 공고 알림 받기]로 공고가 올라오는 날 알려 드릴게요.');
  return parts.join('\n');
}

function missing(C, r) {
  const m = [...(C.unsupported || []).map(u => / — /.test(u) ? u : u + ' — 청약패스에 이 데이터가 없어 답하지 않았어요')];   // 이미 이유를 적은 항목은 덧붙이지 않음
  if (C.conds.some(c => c.key === 'rooms')) m.push('방·욕실 수 — 아직 공고문에서 모으지 않아, 해당 후보는 \'구조 확인 필요\'로 따로 뒀어요');
  for (const c of C.conds.filter(c => c.key === 'commute')) m.push(r.commuted ? c.value.place + ' 대중교통 시간 — 아직 연결하지 않았어요(자동차 시간만, 조회 시각의 교통 기준)' : c.value.place + ' 출퇴근 시간 — 경로 조회를 아직 연결하지 않아, 직선거리로만 순서를 봤어요(시간으로 바꾸지 않음)');
  if (C.conds.some(c => c.key === 'eligible_only') && !r.profile) m.push('내 자격 — 내 조건을 넣지 않아 판정하지 못했어요');
  return m;
}

function nextSteps(C, r, profile) {
  const s = [], a = C.assume || {};
  if (a.kids && !profile) s.push('막내 생일을 알려 주시면 신생아 특별공급(공고일 기준 2세 미만 자녀)·신혼부부 특별공급까지 판정해 드려요');
  // 좁혀 줄 질문 하나 — 아직 모르는 것 중 가장 효과 큰 것 (사용자 예시: '20평대와 30평대 중 어느 쪽에…')
  const has = k => C.conds.some(c => c.key === k || (k === 'price' && /^price/.test(c.key)));
  const ask1 = !has('area') ? '20평대(전용 59㎡)와 30평대(전용 84㎡) 중 어느 쪽에 마음이 기우시는지 알려 주시면 더 좁혀 드릴게요'
    : !has('region_in') ? '살고 싶은 지역이나 출퇴근하는 곳을 알려 주시면 더 좁혀 드릴게요'
    : !has('price') ? '쓸 수 있는 예산(분양가 기준)을 알려 주시면 더 좁혀 드릴게요'
    : !has('commute') ? '출퇴근하는 곳을 알려 주시면 출퇴근 시간까지 따져 드릴게요'
    : '가격·시세 차익·당첨 가능성 중 무엇을 가장 중요하게 보시는지 알려 주시면 한 곳으로 좁혀 드릴게요';
  s.push(ask1);
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
    if (!t.found) continue;
    for (const n of t.notices) blocks.push(card(n.pick, { profile }) + (n.all.length > 1 ? '\n(주택형 ' + n.all.length + '개: ' + n.all.sort((a, b) => a.area - b.area).map(a => a.unit + ' ' + fmtEok(a.price)).join(' · ') + ')' : ''));
  }
  const found = cmp.filter(t => t.found).flatMap(t => t.notices.map(n => n.pick));
  if (!found.length) out.push('결론부터 말씀드리면, 말씀하신 단지들은 청약패스에서 비교해 드릴 수 없어요. 청약패스는 새 분양(청약) 공고만 다루고, 이미 지어진 아파트의 매매·전세 시세는 갖고 있지 않아요. 단지별 실거래가는 국토교통부 실거래가 공개시스템(rt.molit.go.kr)에서 볼 수 있어요. 대신 같은 동네에 새 청약 공고가 나오면 자격·분양가·시세 차익까지 따져 드릴게요.');
  if (found.length >= 2) {
    const bestM = found.slice().sort((a, b) => (b.f.margin.lo ?? -99) - (a.f.margin.lo ?? -99))[0], cheap = found.slice().sort((a, b) => a.f.price.v - b.f.price.v)[0];
    out.push('결론부터 말씀드리면, 시세 차익(추정)은 ' + bestM.f.name + ' ' + bestM.f.unit + '이 가장 크고, 분양가는 ' + cheap.f.name + ' ' + cheap.f.unit + '이 가장 낮아요.' + (found.some(x => x.elig) ? ' 내 자격은 아래 지표의 \'내 자격\' 줄을 보세요.' : ''));
  }
  const nf = cmp.filter(t => !t.found).map(t => t.query);
  if (nf.length && found.length) blocks.unshift('청약패스 공고(지금·지난 1년)에 없는 단지: ' + nf.join(', ') + ' — 이미 지어진 아파트는 비교하지 못해요.');   // 한 번에 묶어서 (AI 심사 회차 3: '찾지 못했어요' 세 번 반복)
  if (!blocks.length) return out;
  out.push('[단지별 핵심 지표' + (cmp.some(t => t.found && t.notices.some(n => n.big)) ? ' · 가장 큰 주택형 기준' : ' · 84㎡에 가까운 주택형 기준') + ']\n\n' + blocks.join('\n\n'));
  return out;
}
