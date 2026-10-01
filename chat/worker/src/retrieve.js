// 청약 전반 질문용 근거 찾기 (2026-10-02): 법령(docs/chat-law.json) + 보고 있는 공고의 모집공고문 조각(docs/chat-notice/<번호>.json).
// 유사도 모델 없이 낱말 겹침 점수로 고른다. 질문 낱말을 청약 용어로 넓혀(서류 → 제출서류·등본·증명서 …) 찾는다.
const SYN = [
  [/서류|준비물|제출|구비/, ['서류', '제출', '증명서', '등본', '확인서', '구비서류', '발급']],
  [/일정|언제|접수|발표|계약일|기간/, ['일정', '접수', '발표', '계약', '기간']],
  [/계약금|중도금|잔금|납부|대출/, ['계약금', '중도금', '잔금', '납부', '대출']],
  [/1순위|순위/, ['순위', '1순위', '제1순위', '2순위']],
  [/가점|점수/, ['가점', '무주택기간', '부양가족', '가입기간', '별표']],
  [/특공|특별공급/, ['특별공급']], [/신혼/, ['신혼부부']], [/생애|생초/, ['생애최초']], [/다자녀/, ['다자녀']], [/노부모/, ['노부모']], [/신생아|출산/, ['신생아', '출산']],
  [/재당첨|당첨\s*제한/, ['재당첨', '당첨']], [/무주택|집이?\s*있|주택\s*소유|유주택/, ['무주택', '소유', '주택']],
  [/통장|예치금|청약저축/, ['주택청약종합저축', '예치', '가입', '청약통장']], [/소득/, ['소득', '월평균소득']], [/자산|부동산|자동차/, ['자산', '부동산', '자동차']],
  [/전매|팔/, ['전매']], [/거주|실거주|전입/, ['거주', '해당지역']], [/세대주/, ['세대주']], [/무순위|잔여|줍줍/, ['무순위', '사후접수', '잔여']],
  [/부적격/, ['부적격']], [/추첨/, ['추첨']], [/분양가|금액|가격/, ['분양가', '공급금액']], [/발코니|옵션/, ['발코니', '선택품목']],
];
const STOP = new Set(['이거', '이건', '뭐야', '뭐예요', '알려줘', '알려주세요', '어떻게', '나는', '제가', '저는', '공고', '이번', '그럼', '근데', '해줘', '되나요', '돼요', '있나요', '있어', '필요한']);

export function terms(question) {
  const q = String(question || '');
  const out = new Map();
  for (const [re, ws] of SYN) if (re.test(q)) ws.forEach(w => out.set(w, 1));
  for (const w of q.split(/[\s?!.,·]+/)) { const t = w.replace(/(은|는|이|가|을|를|에|의|도|요|야|해|나요|인가요|이에요|예요)$/, ''); if (t.length >= 2 && !STOP.has(t)) out.set(t, 3); }   // 질문에 직접 쓴 낱말이 넓힌 낱말보다 무겁다
  return out;
}

function score(text, head, ts) {
  let s = 0;
  for (const [t, w] of ts) { const n = text.split(t).length - 1; if (n) s += w * Math.min(n, 4) + (head && head.includes(t) ? 3 * w : 0); }
  return s;
}

export function pick(list, ts, { max = 5, chars = 4500, get = c => c.t, head = c => c.h, bonus = () => 0 } = {}) {
  const scored = list.map((c, i) => ({ c, i, s: score(get(c), head(c), ts) + bonus(c) })).filter(x => x.s > 0).sort((a, b) => b.s - a.s || a.i - b.i);
  const out = []; let n = 0;
  for (const x of scored) { if (out.length >= max || n + get(x.c).length > chars) continue; out.push(x); n += get(x.c).length; }
  return out.sort((a, b) => a.i - b.i).map(x => x.c);   // 원문 순서대로
}

// 자주 묻는 주제는 핵심 조문을 먼저 (낱말 겹침만으로는 다른 조문이 앞설 때가 있다)
const PIN = [
  [/[12]\s*순위|(?<!무)순위\s*(조건|요건)/, ['제27조', '제28조']], [/가점|점수/, ['별표 1', '제28조']], [/통장|예치금/, ['별표 2', '제28조']],
  [/특공|특별공급/, ['제35조', '제36조', '제40조', '제41조', '제43조', '제46조', '제55조']], [/신혼/, ['제41조']], [/생애|생초/, ['제43조']], [/다자녀/, ['제40조']], [/노부모/, ['제46조']], [/신생아/, ['제41조의2', '제35조의3']],
  [/재당첨/, ['제54조']], [/부적격/, ['제58조']], [/무주택|주택\s*소유|분양권/, ['제53조', '제2조']], [/무순위|사후접수|잔여/, ['제19조', '제47조의3']], [/한\s*번|1회|횟수|평생|두\s*번/, ['제55조']],
];
const pinned = q => { const m = new Map(); for (const [re, arts] of PIN) if (re.test(q)) arts.forEach(a => m.set(a, (m.get(a) || 0) + 1)); return m; };   // 여러 주제에 걸린 조문일수록 앞

// law: {chunks:[{id,art,title,text}]}, notice: {name,pdf,chunks:[{h,t}]}
export function selectGeneral({ law, notice, question, engineItems, lawMax = 3, noticeMax = 6 }) {
  const ts = terms(question), ev = [];
  (engineItems || []).forEach((it, i) => ev.push({ id: 'E' + (i + 1), kind: 'engine', title: '청약패스 판정: ' + it.k, text: [it.k, it.v, it.note].filter(Boolean).join(' · '), s: it.s, cause: it.cause || null }));
  if (notice && notice.chunks) pick(notice.chunks, ts, { max: noticeMax }).forEach((c, i) => ev.push({ id: 'N' + (i + 1), kind: 'notice', tag: c.h || '', title: notice.name + ' 모집공고문', url: notice.pdf, text: (c.h && !c.t.startsWith(c.h) ? c.h + '\n' : '') + c.t }));
  const pins = pinned(String(question || ''));
  if (law && law.chunks && /특공|특별공급/.test(question || '') && /종류|뭐|무엇|어떤|목록/.test(question || '')) {   // '특별공급 종류' — 조문 제목 목록을 근거로
    const seen = new Set(), list = law.chunks.filter(c => /특별공급$/.test(c.title) && !seen.has(c.art) && seen.add(c.art)).map(c => `${c.art} ${c.title}`);
    if (list.length) ev.push({ id: 'L0', kind: 'law', tag: '목록', title: `${law.law} 특별공급 조문 목록`, url: law.source, text: list.join('\n') });
  }
  if (law && law.chunks) pick(law.chunks, ts, { max: lawMax, chars: 3000, get: c => c.text, head: c => c.title, bonus: c => pins.has(c.art) ? 40 * pins.get(c.art) - (/-\d+$/.test(c.id) ? 10 : 0) : 0 }).forEach((c, i) => ev.push({ id: 'L' + (i + 1), kind: 'law', tag: c.art, title: `${law.law} ${c.art}(${c.title})`, url: law.source, text: c.text }));
  return ev;
}
