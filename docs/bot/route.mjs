// 청약봇 '공고 찾기' 질문 갈래 (기능 bot_find, 2026-10-21 사용자 '공고 찾는 것 + 청약 관련 질문도 답하도록'):
//   find    — 지역·가격·면적·단지 이름 같은 찾기 조건이 있는 질문 → 화면 안 V2 엔진 (공고 검색·비교·자격)
//   general — 제도·요령·용어 질문('얼마 넣는 게 좋아', '어떻게 계산', '~가 뭐야', '기준 알려줘') → 청약봇 서버 /chat (법령·공고문 근거, AI 설명)
//   unsure  — 어느 쪽인지 모르겠으면 화면이 두 버튼으로 묻는다
// 판정은 하지 않는다. 조건 유무는 V2 extract 결과(C)로 본다 — 지역·가격·면적·공급 유형·단지 이름·비교 대상.
const SEARCH_KEYS = new Set(['region_in', 'price_max', 'price_min', 'price_range', 'area', 'supply', 'line', 'commute', 'station_walk', 'school_walk', 'status', 'households_min', 'margin']);
const GENERAL = /(얼마(?:씩|를|나|가)?\s?(?:넣|내|넣는|납입)|(?:넣|내)는\s?(?:게|것이)\s?(?:좋|나아|유리)|어떻게\s?(?:계산|세|산정|하|되|되는|돼)|(?:이|가|은|는)?\s?뭐(?:야|예요|에요|죠|임|지)|무슨\s?뜻|뜻이|차이(?:가|는)?\s?(?:뭐|무엇|있)|기준(?:이|은|을|이란)?\s?(?:뭐|무엇|어떻|알려|설명|어디)|조건(?:이|은)\s?(?:뭐|무엇|어떻)|설명해|알려\s?줘(?!.*(?:공고|단지|곳|아파트))|언제부터|몇\s?점|점수(?:가|는)?\s?(?:어떻|몇)|인정(?:되|돼|받)|유리해|불리해|순위(?:가|는)?\s?(?:어떻|뭐)|되나요\?$|돼요\?$|인가요\?$|할까요\?$)/;
const FIND = /(찾아|추천|골라|있어\?|있나요|있을까|넣을\s?만한|노려\s?볼|어디가\s?나|어디가\s?좋|비교|뭐가\s?나|당첨\s?가능성|경쟁률\s?낮)/;
const ELIG_ME = /(저|나|내가|제가|우리|저희)\s?.{0,12}(돼요|되나요|될까요|가능해요|가능한가요|가능할까요|신청\s?가능)/;

export function routeQuestion(q, C) {
  const text = String(q || '').trim();
  const keys = new Set((C && C.conds || []).map(c => c.key));
  const hasSearch = [...keys].some(k => SEARCH_KEYS.has(k) && k !== 'supply') || (C && C.targets && C.targets.length >= 1);
  const onlySupply = keys.size === 1 && keys.has('supply');
  const wantsFind = FIND.test(text);
  const general = GENERAL.test(text);
  if (C && C.intent === 'compare' && C.targets && C.targets.length >= 2) return 'find';
  const eligMe = ELIG_ME.test(text) || /(?:특별공급|특공|신청)\s?(?:돼요|되나요|될까요|가능)/.test(text);   // '동탄 신혼부부 특별공급 돼요?' — 조건이 있으면 그 공고로 자격 판정
  if (hasSearch && (wantsFind || eligMe || !general)) return 'find';
  if (hasSearch && general) return 'unsure';            // '서울 59 9억 이하 1순위 조건이 뭐야?' — 찾기인지 제도인지
  if (eligMe && !general) return 'find';     // '저 신혼 특공 돼요?' — 내 조건으로 자격 판정 (공고 카드)
  if (general || onlySupply) return 'general';
  if (wantsFind) return 'find';
  if (C && C.intent === 'explain') return 'general';
  return (C && C.conds && C.conds.length) ? 'find' : 'unsure';
}
