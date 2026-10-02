// 청약패스 화면(docs/index.html) 안에서 쓰는 입구 — 나중에 청약봇 V2 를 화면에 심을 때 (스위치 chatbot_v2).
// 화면이 이미 불러 둔 판정 함수·공고(LISTINGS)·원자료를 그대로 묶는다. 내 조건은 브라우저 밖으로 보내지 않고 여기서 판정한다.
// AI 두 번(조건 해석·설명)만 청약봇 서버(chat/worker)로 보낸다: llm = ({system, user, purpose}) => fetch(CONFIG.chat_api + '/v2/llm', …)
import { ask as askWith } from './index.mjs';

export function fromScreen(W = globalThis, { raw = null, past = [] } = {}) {
  const names = ['fromApi', 'eligBucket', 'eligibility', 'spJudge', 'spTypesFor', 'SP_NAME', 'ELIG_NAME', 'myScore', 'grade', 'GNAME', 'marginText', 'funding', 'statusOf', 'judgeScope', 'genNone', 'isRental', 'isNewlywedTown', 'kindOf', 'regionScore', 'DEFAULT_PROFILE', 'syncHome', 'syncV2'];
  const E = Object.fromEntries(names.map(n => [n, W[n]]));
  const rawById = Object.fromEntries((raw || []).map(x => [x.id, x]));   // docs/listings.json 원자료 (complex·geo·nearby 는 fromApi 가 옮기지 않음)
  const rows = W.LISTINGS.filter(L => !L.sample).map(L => ({ L, raw: rawById[L.id] || {}, past: false }))
    .concat(past.map(x => ({ L: E.fromApi(x), raw: x, past: true, noJudge: !x.notice_read })));
  return { E, rows, today: W.TODAY, profileOf: p => (p ? E.syncV2(E.syncHome(Object.assign({}, E.DEFAULT_PROFILE, p))) : null) };
}
export const ask = askWith;
