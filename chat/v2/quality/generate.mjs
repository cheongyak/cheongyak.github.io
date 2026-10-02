// 정답을 아는 질문 자동 생성: 조각(사람·지역·예산·면적·유형·추가 조건·끝말)을 섞어 질문을 만들고, 조각마다 기대 조건을 붙인다.
// 사람이 쓴 시험지(golden)가 못 덮는 말투 조합에서 해석이 깨지는지 찾는다. 씨앗(seed)이 같으면 같은 질문 — 회차끼리 비교 가능.
const PERSONA = [
  ['', {}], ['신혼부부인데 ', { assume: { married: true } }], ['아이 둘 키우는 ', { assume: { kids: 2 } }],
  ['자녀 1명(3세) 키우고 있고 ', { assume: { kids: 1 } }], ['무주택 4인 가족이에요. ', { assume: { homeless: true } }], ['현금 3억 있는데 ', { assume: { cash: 3 } }],
];
const REGION = [
  ['서울', [{ key: 'region_in', label: '서울' }]], ['경기도', [{ key: 'region_in', label: '경기' }]], ['인천', [{ key: 'region_in', label: '인천' }]],
  ['수도권', [{ key: 'region_in', label: '수도권' }]], ['광명', [{ key: 'region_in', label: '광명시' }]], ['송파', [{ key: 'region_in', label: '송파구' }]],
  ['과천', [{ key: 'region_in', label: '과천시' }]], ['의왕이나 군포', [{ key: 'region_in', label: '의왕시' }, { key: 'region_in', label: '군포시' }]],
  ['광명 철산동', [{ key: 'region_in', label: '철산동' }]], ['위례', [{ key: 'region_in', label: '위례' }]], ['남양주', [{ key: 'region_in', label: '남양주시' }]],
  ['부산', [{ key: 'region_in', label: '부산' }]], ['', []],
];
const EXCL = [['', []], ['분당은 빼고 ', [{ key: 'region_out', label: '분당' }]], ['강남3구 말고 ', [{ key: 'region_out', label: '강남3구' }]]];
const BUDGET = [['', []], [' 9억 이하', [{ key: 'price_max', value: 9 }]], [' 10억 안쪽', [{ key: 'price_max', value: 10 }]], [' 7억 5천 이하로', [{ key: 'price_max', value: 7.5 }]], [' 8-10억으로', [{ key: 'price_max', value: 10 }]], [' 12억까지', [{ key: 'price_max', value: 12 }]]];
const SIZE = [['', []], [' 국평', [{ key: 'area' }]], [' 30평대', [{ key: 'area' }]], [' 59타입', [{ key: 'area' }]], [' 소형', [{ key: 'area' }]]];
const SUPPLY = [['', []], [' 신혼부부 특공으로', [{ key: 'supply', value: 'sp:newlywed' }]], [' 무순위', [{ key: 'supply', value: 'remainder' }]], [' 공공분양', [{ key: 'supply', value: 'public' }]], [' 생애최초 특공', [{ key: 'supply', value: 'sp:first' }]], [' 신혼희망타운', [{ key: 'supply', value: 'town' }]]];
const EXTRA = [['', []], [', 역세권이면 좋겠어', [{ key: 'station_walk', weight: 'preferred' }]], [', 초품아 위주로', [{ key: 'school_walk' }]], [', 나홀로는 빼고', [{ key: 'not_single', weight: 'required' }]],
  [', 500세대 이상', [{ key: 'households_min', value: 500 }]], ['. 남편 직장 강남역, 아내 판교예요', [{ key: 'commute', weight: 'explore', who: '남편' }, { key: 'commute', weight: 'explore', who: '아내' }]], [', 방3화2 꼭', [{ key: 'rooms', weight: 'required' }]]];
const END = [' 청약 추천해줘', ' 넣을 만한 곳 있어?', ' 알려줘', ' 공고 찾아줘'];

function rng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
export function generate(n = 120, seed = 20261003) {
  const r = rng(seed), pick = a => a[Math.floor(r() * a.length)], out = [], seen = new Set();
  for (let i = 0; out.length < n && i < n * 20; i++) {
    const P = pick(PERSONA), Rg = pick(REGION), X = Rg[0] ? pick(EXCL) : EXCL[0], B = pick(BUDGET), S = pick(SIZE), T = pick(SUPPLY), E = pick(EXTRA), N = pick(END);
    if (!Rg[0] && !B[0] && !S[0] && !T[0]) continue;   // 조건 하나도 없는 질문은 빼고
    if (X[0] && X[1][0].label === '분당' && /분당/.test(Rg[0])) continue;
    const q = (P[0] + X[0] + Rg[0] + B[0] + S[0] + T[0] + E[0] + N).replace(/\s+/g, ' ').trim();
    if (seen.has(q)) continue; seen.add(q);
    const conds = [...Rg[1], ...X[1], ...B[1], ...S[1], ...T[1], ...E[1]];
    out.push({ id: 'gen-' + out.length, q, expect: { intent: 'search', conds, assume: P[1].assume || {}, strict: true } });   // strict: 조각 밖 조건이 생기면 '엉뚱한 조건'
  }
  return out;
}
