// CheckList 행동 테스트 (Ribeiro 외, "Beyond Accuracy: Behavioral Testing of NLP Models with CheckList", ACL 2020).
//  INV(불변): 같은 뜻을 다르게 말해도 조건 해석이 같아야 한다 — 말 바꾸기 표(PARA)로 원문 조각을 바꿔 본다.
//  DIR(방향): 필수 조건을 하나 더하면 후보는 줄거나 같아야 한다(늘면 안 됨). '꼭'을 붙이면 그 조건은 필수가 돼야 한다.
// 말 바꾸기 표는 실제 사용자 말투(샘플·피드백)를 볼 때마다 늘린다 — 이 표가 자랄수록 해석기가 진화한다.
import { extract } from '../extract.mjs';
import { search } from '../search.mjs';

export const PARA = [
  ['9억 이하', ['9억 이내', '9억 아래', '최대 9억', '9억까지', '9억 안쪽', '9억 미만', '9억 넘지 않게']],
  ['국평', ['84타입', '전용 84', '84㎡', '국민평형', '34평']],
  ['경기도', ['경기', '경기권']],
  ['신혼부부 특공으로', ['신혼 특공으로', '신혼부부 특별공급으로', '신특으로']],
  ['생애최초 특공', ['생초 특공', '생애최초 특별공급', '생애 최초 특공']],
  ['무순위', ['줍줍', '무순위 청약', '잔여세대']],
  ['역세권이면 좋겠어', ['역에서 가까우면 좋겠어', '지하철역 가까웠으면 좋겠어', '역세권 선호해']],
  ['초품아 위주로', ['초등학교 가까운 곳 위주로', '초등학교 도보권으로', '초품아면 좋겠어']],
  ['나홀로는 빼고', ['나홀로 아파트 싫어', '나홀로는 제외', '나홀로 말고']],
  ['500세대 이상', ['500세대 넘는', '500세대 이상 단지', '최소 500세대']],
  ['분당은 빼고', ['분당 제외하고', '분당 말고', '분당은 싫고']],
  ['서울', ['서울시', '서울특별시']],
  ['10억 안쪽', ['10억 이하', '10억 이내', '10억 밑으로']],
  ['신혼부부인데', ['결혼 2년차인데', '신혼인데', '신혼부부예요.']],
  ['아이 둘 키우는', ['자녀 2명 키우는', '애 둘 있는', '아이가 둘인']],
];

// 조건 서명: 무엇을 뽑았는지만 비교 (근거 낱말 text 는 말에 따라 다르므로 뺌)
export function sig(C) {
  const cs = C.conds.map(c => c.key + ':' + c.weight + ':' + (Array.isArray(c.value) ? c.value.map(v => v.label || v).sort().join('|') : c.key === 'area' ? 'area' : typeof c.value === 'object' && c.value ? (c.value.place || JSON.stringify(c.value)) : JSON.stringify(c.value))).sort();
  const as = Object.entries(C.assume || {}).filter(([k]) => k !== 'youngest').map(([k, v]) => k + '=' + v).sort();
  return cs.join(' ; ') + ' || ' + as.join(',');
}

export function runINV(questions) {
  const res = [];
  for (const x of questions) for (const [from, tos] of PARA) {
    if (!x.q.includes(from)) continue;
    const base = sig(extract(x.q));
    for (const to of tos) { const q2 = x.q.replace(from, to), s2 = sig(extract(q2)); res.push({ from, to, q: q2, ok: s2 === base, base, got: s2 }); }
  }
  return res;
}

export function runDIR(D, questions, profile = null) {
  const res = [];
  const ADD = [['나홀로는 빼고', 'not_single'], ['9억 이하', 'price_max'], ['국평', 'area'], ['무순위', 'supply']];
  for (const x of questions.slice(0, 60)) {
    const C1 = extract(x.q); if (C1.intent !== 'search') continue;
    const n1 = ids(search(D, C1, { profile, inner: true }));
    for (const [w, key] of ADD) {
      if (x.q.includes(w) || C1.conds.some(c => c.key === key)) continue;
      const C2 = extract(x.q + ', ' + w), n2 = ids(search(D, C2, { profile, inner: true }));
      const extra = [...n2].filter(i => !n1.has(i));
      res.push({ q: x.q, add: w, ok: extra.length === 0 && C2.conds.some(c => c.key === key && c.weight === 'required'), why: extra.length ? '조건을 더했는데 후보가 늘어남 ' + extra.length : !C2.conds.some(c => c.key === key) ? '더한 조건을 못 읽음' : '' });
    }
    // '꼭' 붙이면 필수
    const pref = C1.conds.find(c => c.weight === 'preferred' && c.key === 'station_walk');
    if (pref) { const C3 = extract(x.q.replace(/역세권이면 좋겠어/, '역세권 꼭')); res.push({ q: x.q, add: '꼭', ok: C3.conds.some(c => c.key === 'station_walk' && c.weight === 'required'), why: "'꼭'을 붙여도 필수가 안 됨" }); }
  }
  return res;
}
const ids = r => new Set([...r.ok, ...r.unsure, ...(r.refused || [])].map(x => x.f.id));
