// Claude 호출. 키는 Worker 비밀값(ANTHROPIC_API_KEY)에서만 읽는다. 키는 Console 워크스페이스 안에서 만든 것이어야 함(아니면 400, 10-02).
export const MODEL = 'claude-haiku-4-5-20251001';
// 청약봇 자유 답변(/free)은 Sonnet 5.5 (2026-11-04 운영자: '일반 AI 보다 답이 안 좋다' → 모델 Sonnet 5.5 선택).
// Sonnet 5.5 는 temperature·top_p 를 보내면 400 이라 빼고, 생각(adaptive thinking)은 켜 둔 채 effort 'medium' 으로 줄인다. max_tokens 는 생각+답 합계
export const FREE_MODEL = 'claude-sonnet-5-5';
// 100만 토큰당 달러 [입력, 출력] — 월 한도(CHAT_MONTH_USD) 계산용. 모르는 모델은 비싼 쪽(Sonnet)으로 센다
export const PRICE = { 'claude-haiku-4-5-20251001': [1, 5], 'claude-sonnet-5-5': [2, 10] };
export const usdOf = (model, usage) => { const p = PRICE[model] || [2, 10]; return usage ? ((usage.input_tokens || 0) * p[0] + (usage.output_tokens || 0) * p[1]) / 1e6 : 0; };

export async function callClaude({ apiKey, system, user, fetchImpl = fetch, maxTokens = 1400, model = MODEL, effort = null }) {
  const legacy = /^claude-(haiku|sonnet|opus)-4/.test(model);
  const res = await fetchImpl('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      ...(legacy ? { temperature: 0 } : {}),
      ...(effort && !legacy ? { output_config: { effort } } : {}),
      system: [{ type: 'text', text: system, cache_control: { type: 'ephemeral' } }],
      messages: [{ role: 'user', content: user }],
    }),
  });
  if (!res.ok) {   // 실패 이유(Anthropic 오류 종류·문구)를 남긴다. 키는 들어가지 않음
    let why = '';
    try { const e = await res.json(); why = ((e.error && e.error.type) || '') + ': ' + ((e.error && e.error.message) || ''); } catch (x) {}
    throw new Error('claude ' + res.status + (why ? ' ' + why.slice(0, 160) : ''));
  }
  const j = await res.json();
  const text = (j.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
  return { text, usage: j.usage || null, model, stop: j.stop_reason || null };
}
