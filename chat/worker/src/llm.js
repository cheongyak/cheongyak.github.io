// Claude 호출. 키는 Worker 비밀값(ANTHROPIC_API_KEY)에서만 읽는다.
export const MODEL = 'claude-haiku-4-5-20251001';

export async function callClaude({ apiKey, system, user, fetchImpl = fetch, maxTokens = 900 }) {
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
  if (!res.ok) throw new Error('claude ' + res.status);
  const j = await res.json();
  const text = (j.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
  return { text, usage: j.usage || null };
}
