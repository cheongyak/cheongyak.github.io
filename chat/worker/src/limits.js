// 사용량 제한: 사람마다 하루 2건, 같은 인터넷 주소(IP) 하루 6건, 사이트 전체 하루 상한.
// 되물음에 답한 것은 같은 1건으로 센다(대화에 '되물음 대기' 표시를 남겨 확인).
// Cloudflare KV 는 바로바로 맞춰지지 않아 몇 건 넘칠 수 있다. 비용 상한은 Anthropic 콘솔 월 한도가 최종 장치.
export const LIMITS = { perUser: 2, perIp: 3, global: 100, freeFollowUps: 2 };   // 꼼수 방지: 기기 번호(지우면 새로 생김)와 별도로 같은 인터넷 주소는 하루 3번까지 (집·회사 와이파이를 함께 쓰는 경우 여유 1)   // 되물음 답은 질문 1건당 2번까지만 세지 않는다

const today = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);   // 한국 날짜
const DAY = 60 * 60 * 26;

async function hash(s) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(b)].slice(0, 12).map(x => x.toString(16).padStart(2, '0')).join('');
}

export async function checkLimit(kv, { anonId, ip, conversationId, salt = '' }, limits = LIMITS) {
  const d = today();
  const conv = conversationId ? await kv.get('c:' + conversationId) : null;
  // 되물음에 대한 답: 세지 않음. 다만 답이 계속 되물어도 공짜가 끝없이 이어지지 않게 질문 1건당 freeFollowUps 번까지만
  if (conv && conv.startsWith('ask')) { const n = +(conv.split(':')[1] || 0); if (n < limits.freeFollowUps) return { ok: true, followUp: true, followN: n, remaining: null }; }
  // IP·기기 번호는 비밀 소금(salt)·날짜를 섞어 되돌릴 수 없게 바꾼 값만 둔다 (다음 날 만료)
  const u = 'u:' + d + ':' + await hash('u' + salt + d + anonId), i = 'i:' + d + ':' + await hash('i' + salt + d + ip), g = 'g:' + d;
  const [nu, ni, ng] = (await Promise.all([kv.get(u), kv.get(i), kv.get(g)])).map(x => +(x || 0));
  if (ng >= limits.global) return { ok: false, reason: 'global' };
  if (nu >= limits.perUser || ni >= limits.perIp) return { ok: false, reason: 'user' };
  await Promise.all([kv.put(u, String(nu + 1), { expirationTtl: DAY }), kv.put(i, String(ni + 1), { expirationTtl: DAY }), kv.put(g, String(ng + 1), { expirationTtl: DAY })]);
  return { ok: true, followUp: false, remaining: limits.perUser - nu - 1 };
}

export async function markConversation(kv, conversationId, asked, followN = 0) {
  if (!conversationId) return;
  if (asked) await kv.put('c:' + conversationId, 'ask:' + followN, { expirationTtl: DAY });
  else await kv.delete('c:' + conversationId);
}

export const LIMIT_TEXT = {
  user: '오늘 질문 2건을 모두 쓰셨어요. 내일 다시 물어봐 주세요.',
  global: '오늘 질문이 마감됐어요. 내일 다시 물어봐 주세요.',
};
