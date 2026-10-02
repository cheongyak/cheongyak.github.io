// 질문 → 조건 (규칙 해석). AI 해석(llm.mjs)이 실패하거나 없을 때 쓰고, AI 결과를 검사할 때 기준으로도 쓴다.
// 모든 조건은 { key, value, weight: required|preferred|explore, text } — text 는 질문 속 근거 낱말(답의 '이렇게 이해했어요'에 그대로 보임).
// 형식 밖 조건은 unsupported 로 돌려주고 지어내지 않는다.
import { SIDO, SIDO_ALIAS, DISTRICTS, AREAS, GROUPS, PLACES, SP_WORDS, REQUIRED_WORDS, PREFER_WORDS, EXPLORE_WORDS } from './lexicon.mjs';

const WEIGHT_DEFAULT = { region_in: 'required', region_out: 'required', price_max: 'required', price_min: 'preferred', area: 'required', households_min: 'required',
  not_single: 'required', rooms: 'required', station_walk: 'preferred', school_walk: 'preferred', commute: 'explore', supply: 'required', status: 'required',
  eligible_only: 'required', margin: 'preferred', new_build: 'preferred' };

const num = s => parseFloat(String(s).replace(/,/g, ''));
// '20억' '15억5천' '9억 5,000' '7.5억' '8000만' → 억
export function eok(s) {
  const t = String(s).replace(/\s+/g, '');
  let m = t.match(/^(\d+(?:\.\d+)?)억(?:(\d+(?:,\d{3})?)(?:천)?(만)?)?$/);
  if (m) { let v = num(m[1]); if (m[2]) { const r = num(m[2]); v += /천/.test(t) ? r / 10 : r >= 1000 ? r / 10000 : r / 10; } return Math.round(v * 10000) / 10000; }
  m = t.match(/^(\d+(?:,\d{3})*)만(?:원)?$/); if (m) return num(m[1]) / 10000;
  m = t.match(/^(\d+(?:\.\d+)?)천(?:만)?$/); if (m) return num(m[1]) / 10;
  return null;
}

function clauses(q) {
  // 절 나누기: 문장부호·줄바꿈·'그리고'·'~고 '·'~인데'·'~이면서'
  return q.replace(/\s+/g, ' ').split(/[!?\n·;]|(?<!\d),|,(?!\d)|(?<!\d)\.|\.(?!\d)|그리고|그런데|하고 |이고 |인데 |은데 |는데 |이면서 |면서 |지만 |(?<=겠)고 |(?<=좋)고 /).map(s => s.trim()).filter(Boolean);
}
function weightOf(clause, key) {
  const has = ws => ws.some(w => clause.includes(w));
  if (/(제외|빼고|말고|싫|안\s?돼|절대|꼭|반드시|필수|무조건|여야)/.test(clause) && !/(아니어도|상관없|괜찮)/.test(clause)) return 'required';
  if (has(EXPLORE_WORDS)) return 'explore';
  if (has(PREFER_WORDS)) return 'preferred';
  return WEIGHT_DEFAULT[key] || 'preferred';
}

function findRegions(cl) {
  const out = [];
  for (const [g, ds] of Object.entries(GROUPS)) if (cl.includes(g)) ds.forEach(d => out.push({ sido: '서울', district: d, label: g }));
  for (const [name, a] of Object.entries(AREAS)) if (cl.includes(name) && !Object.keys(GROUPS).some(g => g.startsWith(name) && cl.includes(g)) && !new RegExp(name + '\\s?(역|까지|으로|로)?\\s?(출퇴근|출근|통근)').test(cl) && !new RegExp(name + '(역)?\\s?까지').test(cl)) out.push({ sido: a.sido, district: a.district || null, words: a.words, label: name, lat: a.lat, lng: a.lng });
  for (const [sd, dn, lat, lng] of DISTRICTS) {
    const short = dn.replace(/(특례시|시|군|구)$/, '');
    const re = new RegExp('(^|[^가-힣])(' + dn + (short.length >= 2 ? '|' + short + '(?=[^가-힣]|$|에|에서|쪽|권|이나|나|이|가|은|는|도|만|을|를|면|랑|하고|으로|로|동네|근처|살)' : '') + ')');
    if (re.test(cl) && !out.some(o => o.district === dn || o.label === short)) out.push({ sido: sd, district: dn, label: dn, lat, lng });
  }
  for (const [k, full] of Object.entries(SIDO)) if (new RegExp('(^|[^가-힣])(' + k + '|' + full + ')(?![가-힣]*구)').test(cl) && !out.some(o => o.sido === k)) out.push({ sido: k, district: null, label: k });
  for (const [a, k] of Object.entries(SIDO_ALIAS)) if (cl.includes(a)) {
    if (k === null) ['서울', '경기', '인천'].forEach(s => { if (!out.some(o => o.sido === s && !o.district)) out.push({ sido: s, district: null, label: '수도권' }); });
    else if (!out.some(o => o.sido === k)) out.push({ sido: k, district: null, label: k });
  }
  // 동 이름 ('철산동', '개봉동이나 고척동') — 주소 낱말로 찾는다. 같은 절의 시·군·구는 그 동의 상위로만 쓴다
  const dongs = [...cl.matchAll(/(^|[^가-힣])([가-힣]{1,4}\d?동)(?=$|[^가-힣]|이나|이랑|이|에|쪽|은|는|도|과|와|,)/g)].map(m => m[2]).filter(d => !/^(같은|이|그|저|어느|아무|자동|행동|운동|활동|이동|공동|합동|단독|변동|연동|작동|감동|노동|충동|세대동|개동)$/.test(d) && !/개동$/.test(d));
  if (dongs.length) {
    const parents = out.filter(o => o.district);
    for (const d of dongs) {
      const par = parents.find(p => cl.indexOf(p.label.replace(/(시|구|군)$/, '')) >= 0 && cl.indexOf(p.label.replace(/(시|구|군)$/, '')) < cl.indexOf(d)) || null;
      out.push({ sido: par ? par.sido : null, district: null, parent: par ? par.district : null, words: [d], label: d, lat: par ? par.lat : null, lng: par ? par.lng : null });
    }
    return out.filter(o => !(o.district && parents.includes(o)));
  }
  // '서울 송파'처럼 시·도와 구가 같이 오면 구만 남긴다
  return out.filter(o => o.district || !out.some(p => p !== o && p.sido === o.sido && p.district));
}

// '구로' '마포' '판교' → 출퇴근 목적지 좌표. 역 이름이 없으면 시·군·구 중심(근사)을 쓰고 '가정'으로 표시
function placeOf(w) {
  if (PLACES[w]) return PLACES[w];
  const d = DISTRICTS.find(x => x[1] === w || x[1].replace(/(특례시|시|구|군)$/, '') === w);
  return d ? { name: d[1] + ' (중심 근사)', lat: d[2], lng: d[3], approx: true } : null;
}

export function extract(question) {
  const q = String(question || '').trim();
  const C = { intent: 'search', targets: [], conds: [], assume: {}, perspectives: [], unsupported: [], scope: { past: false }, q };
  const add = (key, value, clause, text, weight) => C.conds.push({ key, value, weight: weight || weightOf(clause, key), text: text || clause });
  const cls = clauses(q);

  // 비교: 'A vs B', 'A랑 B 비교', 'A와 B 중'
  const vs = q.split(/\s*(?:vs\.?|VS|대|와|과|랑|하고)\s+(?=\S)/);
  if (/(vs|VS|비교|중에\s?(뭐|어디)|어디가 (나아|좋아|낫))/.test(q)) C.intent = 'compare';
  if (/(가점|점수).*(몇|얼마|계산)|내 가점/.test(q)) C.intent = C.intent === 'compare' ? 'compare' : 'score';
  if (/(뭐야|뭔가요|무엇|설명|차이가 뭐|란\??$|이란)/.test(q) && !/(추천|찾아|알려줘.*(공고|단지))/.test(q)) C.intent = 'explain';

  for (const cl of cls) {
    // 지역 (포함/제외)
    const excl = /(제외|빼고|말고|싫|아니어도|아닌)/.test(cl);
    // 직장 위치 ('남편 직장 구로', '아내 마포', '회사는 판교') — 지역 조건이 아니라 출퇴근 목적지
    const WP = /(남편|아내|와이프|신랑|배우자|제|저|내|나|우리)?\s?(?:의\s?)?(직장|회사|근무지|출근지|일터)?\s?(?:은|는|이|가)?\s?([가-힣]{2,6}?)(?:역)?\s?(?:이고|이에요|예요|이며|에서 일|으로 출근|로 출근|에 다녀|에 있어|,|$)/;
    let clR = cl;
    for (const m of cl.matchAll(new RegExp(WP.source, 'g'))) {
      if (!m[1] && !m[2]) continue;
      const place = placeOf(m[3]); if (!place) continue;
      if (!C.conds.some(c => c.key === 'commute' && c.value.place === place.name && c.value.who === (m[1] || ''))) add('commute', { place: place.name, lat: place.lat, lng: place.lng, max_min: null, who: m[1] || '', approx: place.approx }, cl, (m[1] ? m[1] + ' ' : '') + '직장 ' + place.name + (place.approx ? '(가정)' : ''), 'explore');
      clR = clR.replace(m[0], ' ');
    }
    // '강남3구 말고 서울에서' — 제외 낱말 앞의 지역만 제외, 뒤는 포함
    const ex = clR.match(/^(.*?)(제외|빼고|말고)(.*)$/), exA = ex ? findRegions(ex[1]) : [], exB = ex ? findRegions(ex[3]) : [];
    if (exA.length && exB.length) {
      add('region_out', exA, cl, exA.map(r => r.label).filter((x, i, y) => y.indexOf(x) === i).join('·') + ' 제외', 'required');
      add('region_in', exB, ex[3], exB.map(r => r.label).filter((x, i, y) => y.indexOf(x) === i).join('·'));
    }
    const regs = exA.length && exB.length ? [] : findRegions(clR);
    if (regs.length) {
      if (excl && /(제외|빼고|말고|싫)/.test(cl)) add('region_out', regs, cl, regs.map(r => r.label).filter((x, i, a) => a.indexOf(x) === i).join('·') + ' 제외', 'required');
      else if (/아니어도|상관없|괜찮|근처|주변|인접/.test(cl)) add('region_in', regs, cl, regs.map(r => r.label).filter((x, i, a) => a.indexOf(x) === i).join('·') + (/(근처|주변|인접)/.test(cl) ? ' 근처' : ' (아니어도 됨)'), 'explore');
      else { const rs = regs.filter(r => !(/(출퇴근|출근|통근|직장|회사)/.test(cl) && (PLACES[r.label] || PLACES[String(r.label).replace(/(시|구)$/, '')])));
        if (rs.length) add('region_in', rs, cl, rs.map(r => r.label).filter((x, i, a) => a.indexOf(x) === i).join('·')); }
    }
    // 예산·분양가
    let m = cl.match(/(\d+(?:\.\d+)?\s?억(?:\s?\d+(?:,\d{3})?\s?(?:천|만)?)?|\d+(?:,\d{3})*\s?만\s?원?)\s?(?:원)?\s?(이하|이내|까지|미만|안쪽|아래|넘지|선에서|정도|내외|이상|넘는|부터|초과|대)/);
    if (m && !/(현금|자금|모은|보유|가지고|있어|연봉|소득|전세금)/.test(cl.slice(0, cl.indexOf(m[0])))) {
      const v = eok(m[1]);
      if (v != null) {
        if (/이상|넘는|부터|초과/.test(m[2])) add('price_min', v, cl, m[0]);
        else if (m[2] === '대') add('price_range', [v, v + (v >= 10 ? 1 : 1)], cl, m[0], weightOf(cl, 'price_max'));
        else add('price_max', v, cl, m[0], /정도|내외|선에서/.test(m[2]) ? 'preferred' : undefined);
      }
    }
    const rg = cl.match(/(\d+(?:\.\d+)?)\s?(?:억)?\s?[-~∼에서]\s?(\d+(?:\.\d+)?)\s?억\s?(?:원)?\s?(?:사이|대|까지|정도|으로|로|이내|안쪽)?/);
    if (rg && !/(현금|자금|모은|보유|연봉|소득)/.test(cl.slice(0, cl.indexOf(rg[0]))) && +rg[1] < +rg[2]) { C.conds = C.conds.filter(c => !/^price_/.test(c.key)); add('price_max', +rg[2], cl, rg[1] + '~' + rg[2] + '억(최대 ' + rg[2] + '억)', 'required'); }   // 예산 범위는 위쪽만 거른다 — 더 싼 곳을 빼지 않음
    // 내 돈 (이번만의 가정)
    m = cl.match(/(현금|자금|모은\s?돈|가용\s?자금|보유\s?자금|가진\s?돈|자기자본)\s?(?:이|은|는)?\s?(\d+(?:\.\d+)?\s?억(?:\s?\d+(?:,\d{3})?\s?(?:천|만)?)?|\d+(?:,\d{3})*\s?만)/);
    if (m) C.assume.cash = eok(m[2]);
    m = cl.match(/(연봉|소득|월급)\s?(?:이|은|는)?\s?(\d+(?:,\d{3})*|\d+(?:\.\d+)?억)\s?(만)?/);
    if (m) C.assume.income = /억/.test(m[2]) ? eok(m[2]) * 10000 : num(m[2]);
    // 면적
    if (/국평|국민평형/.test(cl)) add('area', { min: 75, max: 86, label: '국민평형(전용 84㎡)' }, cl, '국평');
    m = cl.match(/(?:전용\s?)?(\d{2,3}(?:\.\d+)?)\s?(㎡|m2|제곱미터|타입|형)(?!\s?세대)/);
    if (m) { const a = num(m[1]); add('area', { min: a - 3, max: a + 3, label: '전용 ' + a + '㎡ 안팎' }, cl, m[0]); }
    m = cl.match(/(\d{2})\s?평\s?(대|이상|이하)?/);
    if (m && !/㎡/.test(cl)) { const p = num(m[1]); const supply2ex = x => Math.round(x * 3.3058 * 0.76);   // 공급면적 평 → 전용 근사(전용률 76%)
      const lo = m[2] === '대' ? supply2ex(Math.floor(p / 10) * 10) : m[2] === '이하' ? 0 : supply2ex(p) - 6, hi = m[2] === '대' ? supply2ex(Math.floor(p / 10) * 10 + 10) : m[2] === '이상' ? 400 : supply2ex(p) + 6;
      add('area', { min: lo, max: hi, label: m[0].replace(/\s/g, '') + '(전용 약 ' + lo + '~' + hi + '㎡, 평은 공급면적 기준 근사)', approx: true }, cl, m[0]); }
    if (/(소형|작은 평수)/.test(cl)) add('area', { min: 0, max: 60, label: '전용 60㎡ 이하' }, cl, '소형');
    if (/(대형|큰 평수|넓은 집)/.test(cl)) add('area', { min: 85.0001, max: 400, label: '전용 85㎡ 초과' }, cl, '대형');
    // 단지 규모
    m = cl.match(/(\d{1,3}(?:,\d{3})+|\d{2,5})\s?세대\s?(이상|넘|부터)/);
    if (m) add('households_min', num(m[1]), cl, m[0]);
    if (/대단지/.test(cl) && !m) add('households_min', 1000, cl, '대단지', weightOf(cl, 'x') === 'required' ? 'required' : 'preferred');
    if (/나홀로/.test(cl)) add('not_single', true, cl, '나홀로 제외', 'required');
    // 방·욕실
    m = cl.match(/방\s?(\d)\s?(?:개)?\s?(?:,|\s)?\s?(?:화|화장실|욕실)\s?(\d)/) || cl.match(/방\s?(\d)\s?(?:개)?/) || cl.match(/(쓰리|투)룸/);
    if (m) { const bed = m[1] === '쓰리' ? 3 : m[1] === '투' ? 2 : +m[1], bath = m[2] ? +m[2] : null; add('rooms', { bed, bath }, cl, m[0]); }
    // 역·학교
    if (/역세권|역\s?(가까|도보|근처)|지하철\s?(가까|도보)/.test(cl)) { const w = cl.match(/(\d{1,2})\s?분/); add('station_walk', w ? +w[1] : 10, cl, w ? '역 도보 ' + w[1] + '분' : '역세권(도보 약 10분)'); }
    if (/초품아|초등학교|초등|학교\s?(가까|도보|근처)/.test(cl)) { const w = cl.match(/(\d{1,2})\s?분/); add('school_walk', { kind: '초등학교', min: w ? +w[1] : 10 }, cl, w ? '초등학교 도보 ' + w[1] + '분' : '초등학교 가까이(도보 약 10분)'); }
    // 출퇴근
    if (/(출퇴근|출근|통근|직장|회사)/.test(cl)) for (const [k, p] of Object.entries(PLACES)) {   // '판교나 의왕으로 출퇴근' — 그 절의 장소 모두
      if (new RegExp(k + '(?![가-힣]*구)').test(cl) && !C.conds.some(c => c.key === 'commute' && c.value.place === p.name)) { const w = cl.match(/(\d{1,3})\s?분/); add('commute', { place: p.name, lat: p.lat, lng: p.lng, max_min: w ? +w[1] : null }, cl, p.name + ' 출퇴근' + (w ? ' ' + w[1] + '분' : '')); }
    }
    // 공급 유형
    for (const [w, t] of Object.entries(SP_WORDS)) if (new RegExp(w + '\\s?(특공|특별공급|으로|로|자격|전형)').test(cl) && !C.conds.some(c => c.key === 'supply' && c.value === 'sp:' + t)) add('supply', 'sp:' + t, cl, w + ' 특별공급', 'preferred');
    if (/(무순위|줍줍|잔여세대|청약통장 없이)/.test(cl)) add('supply', 'remainder', cl, '무순위(줍줍)');
    if (/신혼희망타운|신희타/.test(cl)) add('supply', 'town', cl, '신혼희망타운');
    if (/공공분양|국민주택/.test(cl)) add('supply', 'public', cl, '공공분양');
    if (/민영|민간분양/.test(cl)) add('supply', 'private', cl, '민영');
    if (/(임대)/.test(cl) && !/(토지임대)/.test(cl)) add('supply', 'rental', cl, '공공임대');
    // 상태
    if (/(지난|과거|마감된|예전|작년|최근 \d+년|당첨선|당첨 가점|커트라인|컷)/.test(cl)) C.scope.past = true;
    if (/(접수\s?중|지금 넣을|오늘|이번 주)/.test(cl)) add('status', ['접수 중'], cl, '접수 중');
    else if (/(예정|다가오는|곧|다음 달|앞으로)/.test(cl) && !/(상승|오를)/.test(cl)) add('status', ['접수 예정'], cl, '접수 예정');
    // 내 자격으로 거르기
    if (/(내가|제가|저도|나도|우리).{0,10}(넣을|신청|당첨될|자격|가능)|자격\s?(되는|있는|맞는)|신청\s?가능한|넣을\s?수\s?있는/.test(cl)) add('eligible_only', true, cl, '내 자격으로 신청 가능한 곳', 'required');
    // 이번만의 가정 (내 조건 칸과 따로)
    if (/(신혼부부|결혼\s?\d년|예비\s?신혼|결혼했)/.test(cl) && /(신혼부부|결혼\s?\d년|예비\s?신혼|결혼했)\s?(이에요|입니다|인데|이고|예요|라|이라|이야|임|$)/.test(q)) C.assume.married = true;
    if (/(무주택)(이에요|입니다|인데|이고|이라|자)/.test(cl)) C.assume.homeless = true;
    if (/(유주택|집이 있|1주택)/.test(cl)) C.assume.homeless = false;
    m = cl.match(/(아이|자녀|애|아기)\s?(\d)\s?(명|둘|셋)?/); if (m) C.assume.kids = +m[2];
    m = cl.match(/(\d{1,2})\s?(세|살|개월)/); if (m && /(아이|자녀|애|아기|양육|키우)/.test(cl)) C.assume.youngest = m[1] + m[2];   // 생일을 모르니 판정에 넣지 않고 되묻는다
    // 관점
    if (/(시세\s?차익|마진|로또|안전마진|싸게)/.test(cl)) { add('margin', 'consider', cl, '시세 차익(마진)', 'preferred'); C.perspectives.push('margin'); }
    if (/(당첨\s?(가능성|확률|될|되는)|경쟁률\s?(낮|적))/.test(cl)) C.perspectives.push('chance');
    if (/(가격|저렴|싼|가성비|예산)/.test(cl)) C.perspectives.push('price');
    if (/(신축|새 아파트|새아파트)/.test(cl)) add('new_build', true, cl, '신축', 'preferred');
    // 아직 못 보는 조건 — 지어내지 않고 '확인 불가'로 돌려준다
    for (const [re, label] of [[/(급지|호재|상승\s?여력|오를|투자\s?가치|미래\s?가치)/, '급지·호재·상승 여력(청약패스 데이터 없음)'], [/(주차)/, '주차 대수(데이터 없음)'], [/(학군|학원가|명문)/, '학군·학원가(데이터 없음 — 학교 거리만 있음)'],
      [/(층|향|남향|뷰|조망)/, '층·향·조망(데이터 없음)'], [/(커뮤니티|헬스장|수영장)/, '커뮤니티 시설(데이터 없음)'], [/(구축|재건축|매매|매물|급매)/, '기존 아파트 매매(청약패스는 새 분양 공고만)']])
      if (re.test(cl) && !C.unsupported.includes(label)) C.unsupported.push(label);
  }
  C.perspectives = [...new Set(C.perspectives)];
  // 여러 절의 지역(포함)은 '또는'으로 한 조건에
  { const out = [], seen = {};
    for (const c of C.conds) { if (c.key !== 'region_in') { out.push(c); continue; } const k = c.weight + (c.explore_ok ? '+' : '');
      if (seen[k]) { seen[k].value = seen[k].value.concat(c.value.filter(v => !seen[k].value.some(w => w.label === v.label))); seen[k].text = [...new Set(seen[k].value.map(v => v.label))].join('·'); } else { seen[k] = { ...c, value: c.value.slice() }; out.push(seen[k]); } }
    C.conds = out; }
  // 출퇴근은 분을 말하지 않으면 '넓혀 보기'(순서에만 씀). 분을 말하면 그 무게 그대로
  C.conds.forEach(c => { if (c.key === 'commute' && c.value.max_min == null) c.weight = 'explore'; });
  // 상위 시·군·구가 없는 동: 질문에서 그 앞에 나온 시·군·구를 상위로 ('구로 개봉동, 고척동')
  for (const c of C.conds.filter(c => c.key === 'region_in')) for (const v of c.value) if (v.words && !v.parent && !v.district && !v.sido) {
    const at = q.indexOf(v.label); let best = null;
    for (const [sd, dn, lat, lng] of DISTRICTS) { const sh = dn.replace(/(특례시|시|구|군)$/, ''); if (sh.length < 2) continue; const i = q.lastIndexOf(sh, at); if (i >= 0 && i < at && (!best || i > best.i)) best = { i, sd, dn, lat, lng }; }
    if (best) Object.assign(v, { sido: best.sd, parent: best.dn, lat: best.lat, lng: best.lng });
  }
  // '송파에 살고 싶은데 송파 아니어도 괜찮아' → 송파는 선호, 다른 지역도 탐색
  const rin = C.conds.filter(c => c.key === 'region_in');
  for (const c of rin) if (c.weight === 'explore') {
    const same = rin.find(o => o !== c && o.weight !== 'explore' && o.value.some(v => c.value.some(w => w.label === v.label)));
    if (same) { same.weight = 'preferred'; same.explore_ok = true; c._drop = true; }
  }
  C.conds = C.conds.filter(c => !c._drop);
  if (C.intent === 'compare') C.conds = C.conds.filter(c => c.key !== 'region_in');   // 비교할 단지 이름 속 지명은 지역 조건이 아니다
  if (C.intent === 'compare') C.targets = q.replace(/(비교|해\s?줘|해주세요|부탁|중에\s?(뭐|어디).*$|어디가.*$|\?|!)/g, ' ').split(/\s+(?:vs\.?|VS|대)\s+|\s?(?:랑|이랑|하고|와|과)\s+/).map(s => s.trim()).filter(s => s.length >= 2);
  // 같은 key 가 여러 번이면 마지막(더 구체적인) 것만, 지역은 합침
  const seen = {};
  C.conds = C.conds.filter((c, i) => {
    if (c.key === 'region_in' || c.key === 'region_out' || c.key === 'supply' || c.key === 'commute') return true;
    const last = C.conds.map(x => x.key).lastIndexOf(c.key); return last === i;
  });
  void seen; void vs;
  return C;
}

// 후속 질문: 지금 조건(state)에 바뀐 부분만 더한다. '송파 포기할게' → 송파 조건 삭제, '18억으로' → 예산 교체, '방3 필수' → 추가
export function applyDelta(state, question) {
  const q = String(question || '');
  const next = JSON.parse(JSON.stringify(state || { conds: [], assume: {}, perspectives: [], unsupported: [], scope: { past: false } }));
  const d = extract(q);
  const dropRe = /(포기|빼|없어도|상관없|안 따져|안따져|풀어|무시)/;
  if (dropRe.test(q)) {
    const regs = findRegions(q);
    next.conds = next.conds.filter(c => {
      if ((c.key === 'region_in' || c.key === 'region_out') && regs.length) return !c.value.some(v => regs.some(r => r.label === v.label || (r.district && r.district === v.district)));
      if (c.key === 'rooms' && /방/.test(q)) return false;
      if (c.key === 'households_min' && /세대|대단지/.test(q)) return false;
      if (c.key === 'not_single' && /나홀로/.test(q)) return false;
      if ((c.key === 'price_max' || c.key === 'price_range') && /(예산|가격|억)/.test(q)) return false;
      if (c.key === 'commute' && /출퇴근|출근/.test(q)) return false;
      if (c.key === 'school_walk' && /학교/.test(q)) return false;
      return true;
    });
    d.conds = d.conds.filter(c => !(c.key === 'region_in' || c.key === 'region_out'));
  }
  // '18억으로' 처럼 숫자만 다시 말하면 예산 교체
  const bare = q.match(/(\d+(?:\.\d+)?\s?억)\s?(?:으로|로)/);
  if (bare && !d.conds.some(c => /^price/.test(c.key))) d.conds.push({ key: 'price_max', value: eok(bare[1]), weight: 'required', text: bare[0] });
  for (const c of d.conds) {
    if (['region_in', 'region_out', 'supply', 'commute'].includes(c.key)) next.conds.push(c);
    else next.conds = next.conds.filter(x => x.key !== c.key).concat([c]);
  }
  Object.assign(next.assume, d.assume);
  next.perspectives = [...new Set([...(next.perspectives || []), ...d.perspectives])];
  next.unsupported = [...new Set([...(next.unsupported || []), ...d.unsupported])];
  if (d.scope.past) next.scope = { ...next.scope, past: true };
  if (d.intent !== 'search') next.intent = d.intent;
  next.q = q;
  return next;
}
