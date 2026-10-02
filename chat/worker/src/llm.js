// Claude 호출. 키는 Worker 비밀값(ANTHROPIC_API_KEY)에서만 읽는다.
export const MODEL = 'claude-haiku-4-5-20251001';

export async function callClaude({ apiKey, system, user, fetchImpl = fetch, maxTokens = 1400 }) {
  const res = await fetchImpl('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: maxTokens,
      temperature: 0,
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
  return { text, usage: j.usage || null };
}
