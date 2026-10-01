// 근거 지도: 공고문 발췌(docs/rules-evidence.txt)를 공고번호·태그별로 나누고,
// 엔진 판정 항목에 맞는 조각만 골라 준다. 유사도 검색 없이 '항목 → 태그' 표로 찾는다.

// 엔진 항목 이름(cpExplain 의 k) → 공고문 발췌 태그
const ITEM_TAGS = [
  [/거주/, ['거주기간', '우선공급']],
  [/세대주/, ['1순위']],
  [/무주택/, ['무주택기간']],
  [/통장|가입기간|예치금|납입/, ['가입기간', '예치금액', '납입인정', '청약예금']],
  [/소득/, ['소득기준', '월평균소득']],
  [/자산/, ['자산']],
  [/재당첨|당첨 없음|5년/, ['재당첨', '5년 이내']],
  [/신혼희망타운|신청 유형/, ['신혼부부']],
  [/가점/, ['가점제', '부양가족', '무주택기간']],
  [/추첨/, ['추첨제']],
];
// 특별공급 유형 → 태그
const SP_TAGS = { newborn: '신생아', newlywed: '신혼부부', first: '생애최초', multichild: '다자녀', elder: '노부모', agency: '기관추천' };
// 질문 낱말 → 태그 (엔진이 판정하지 않는 것을 물을 때 공고문으로 답하기 위해)
const WORD_TAGS = [
  [/기관\s*추천|장애|국가유공/, ['기관추천']],
  [/신혼/, ['신혼부부']], [/생애\s*최초|생초/, ['생애최초']], [/다자녀/, ['다자녀']],
  [/노부모/, ['노부모']], [/신생아|출산/, ['신생아']],
  [/추첨/, ['추첨제']], [/가점/, ['가점제', '부양가족']],
  [/소득/, ['소득기준', '월평균소득']], [/자산|부채|자동차/, ['자산']],
  [/통장|예치금|납입/, ['가입기간', '예치금액', '납입인정']],
  [/재당첨|당첨\s*이력/, ['재당첨']], [/거주|전입/, ['거주기간', '우선공급']],
];

export function parseEvidence(text) {
  const byNotice = new Map();
  let cur = null;
  for (const line of text.split('\n')) {
    if (line.startsWith('### ')) {
      const m = /주택관리번호\s+(\d+)/.exec(line);
      cur = m ? { nid: m[1], title: line.slice(4).split(' · ')[0], pdf: null, snippets: [] } : null;
      if (cur) byNotice.set(cur.nid, cur);
    } else if (cur && line.startsWith('PDF: ')) {
      cur.pdf = line.slice(5).split(' · ')[0].trim();
    } else if (cur) {
      const m = /^\[([^\]]+)\]\s*(.+)$/.exec(line);
      if (m) cur.snippets.push({ tag: m[1], text: m[2].replace(/^…|…$/g, '').trim() });
    }
  }
  return byNotice;
}

const nidOf = id => String(id || '').split('-')[0];

// 엔진 결과 + 질문 → 근거 목록. 엔진 항목도 근거(E)로 넣는다: 판정 근거는 엔진이 1순위다.
export function selectEvidence(index, engine, question, { perTag = 2, max = 8 } = {}) {
  const out = [];
  (engine.items || []).forEach((it, i) => {
    out.push({ id: 'E' + (i + 1), kind: 'engine', title: '청약패스 판정: ' + it.k, text: [it.k, it.v, it.note].filter(Boolean).join(' · '), s: it.s, cause: it.cause || null });
  });
  const notice = index.get(nidOf(engine.listing && engine.listing.id));
  if (!notice) return { evidence: out, notice: null };
  const tags = [];
  const add = t => { if (!tags.includes(t)) tags.push(t); };
  // 사용자가 직접 물은 주제가 먼저, 그다음 판정을 가른 항목(fail·warn)
  for (const [re, ts] of WORD_TAGS) if (re.test(question || '')) ts.forEach(add);
  for (const it of engine.items || []) {
    if (it.s !== 'fail' && it.s !== 'warn') continue;
    for (const [re, ts] of ITEM_TAGS) if (re.test(it.k)) ts.forEach(add);
  }
  for (const sp of engine.special || []) if (sp.v !== '불가' && SP_TAGS[sp.type] && new RegExp(SP_TAGS[sp.type]).test(question || '')) add(SP_TAGS[sp.type]);
  let n = 0;
  for (const tag of tags) {
    const pool = notice.snippets.filter(s => s.tag === tag);
    // 같은 태그 안에서는 질문 낱말이 많이 겹치는 조각을 앞으로
    const words = (question || '').split(/\s+/).filter(w => w.length >= 2);
    pool.sort((a, b) => score(b.text, words, tag) - score(a.text, words, tag));
    for (const s of pool.slice(0, perTag)) {
      if (n >= max) break;
      n++;
      out.push({ id: 'N' + n, kind: 'notice', tag, title: notice.title + ' 모집공고문', url: notice.pdf, text: s.text.slice(0, 600) });
    }
  }
  return { evidence: out, notice };
}

function score(text, words, tag) {
  let s = 0;
  for (const w of words) if (text.includes(w)) s += 2;
  const hits = text.split(tag).length - 1;
  return s + Math.min(hits, 3);
}
