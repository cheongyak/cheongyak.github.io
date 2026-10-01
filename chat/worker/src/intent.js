// 질문 유형 분류. 시험 단계는 규칙으로 한다 (AI 호출 1번 절약). 애매하면 'judge'.
const OUT = /(사\s*(도|둬도)\s*(돼|될까|되나)|오를까|떨어질까|투자|매수|매도|팔아야|시세\s*전망|양도세|취득세\s*얼마|종부세|세금\s*얼마|대출\s*(한도|금리)\s*얼마|주식|코인)/;
const SCHEDULE = /(언제|일정|마감|발표|접수일|계약일|잔금|입주)/;
const DOCS = /(서류|증빙|제출)/;
const RULE = /(왜|기준이|기준은|뜻이|뭐야|무슨\s*뜻|어떻게\s*계산|조건이\s*뭐)/;

export function classify(question) {
  const q = String(question || '');
  if (OUT.test(q)) return 'out_of_scope';
  if (DOCS.test(q)) return 'docs';
  if (SCHEDULE.test(q) && !/(가능|되나|돼\?|될까)/.test(q)) return 'schedule';
  if (RULE.test(q) && !/(나|내가|저|제가).{0,6}(가능|돼|될까|되나)/.test(q)) return 'rule';
  return 'judge';
}

export const OUT_OF_SCOPE_TEXT = '이 질문은 청약 자격·공고 안내 범위 밖이라 답하기 어려워요. 매매·투자·세금은 전문가나 공식 기관에 확인해 주세요.';
