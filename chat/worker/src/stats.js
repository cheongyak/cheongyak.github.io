// 하루 합계(개인 식별 없음). KV 's:YYYY-MM-DD' 한 칸에 JSON 으로 더한다. 질문 원문·답변·내 조건은 넣지 않는다.
// KV 는 바로 맞춰지지 않아 동시에 들어오면 몇 건 빠질 수 있다 (참고용 합계).
const today = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
export const FEEDBACK_REASONS = {
  wrong_info: '정보가 틀렸어요', not_answered: '질문에 답하지 않았어요', hard: '이해하기 어려워요', too_long: '너무 길어요',
  no_source: '근거가 부족해요', differs: '공고문과 달라요', other: '기타',
};

export async function bump(kv, add) {
  if (!kv) return;
  const k = 's:' + today();
  let s = {};
  try { s = JSON.parse(await kv.get(k) || '{}'); } catch (e) { s = {}; }
  for (const [key, v] of Object.entries(add)) {
    if (v == null || v === false) continue;
    if (typeof v === 'string') { s[key] = s[key] || {}; s[key][v] = (s[key][v] || 0) + 1; }   // 종류별 세기 (intent·verdict·reason)
    else s[key] = (s[key] || 0) + (v === true ? 1 : +v || 0);
  }
  await kv.put(k, JSON.stringify(s), { expirationTtl: 400 * 86400 });
}

export async function readStats(kv, days = 7) {
  const out = {};
  for (let i = 0; i < days; i++) {
    const d = new Date(Date.now() + 9 * 3600e3 - i * 86400e3).toISOString().slice(0, 10);
    const v = await kv.get('s:' + d);
    if (v) out[d] = JSON.parse(v);
  }
  return out;
}
