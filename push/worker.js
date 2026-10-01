// 청약패스 웹 푸시 알림 서버 (Cloudflare Workers + KV) — 기능: web_push
//
// 하는 일
//   1. 구독 보관: 브라우저가 알림을 켜면 푸시 주소(endpoint)·암호 키와 고른 지역·알림 종류만 KV 에 저장한다.
//      인터뷰 입력값(소득·자산 등)은 받지 않는다.
//   2. 발송: 매일 수집(GitHub Actions)이 끝나면 새 공고·접수 전날 이벤트를 /send 로 보내고,
//      여기서 구독자마다 맞는 것만 골라 한 통으로 묶어 Web Push(RFC 8030/8291/8292)로 보낸다.
//   3. 만료 정리: 푸시 서비스가 404/410 을 주면(브라우저에서 알림을 끄거나 앱을 지움) 그 구독을 바로 지운다.
//
// 키
//   VAPID 키(서버 서명 키)는 처음 요청 때 여기서 만들어 KV 에만 둔다. 비밀 키는 Cloudflare 계정 밖으로 나가지 않는다.
//   /send 는 GitHub Secrets 의 PUSH_SEND_TOKEN 과 같은 값(워커 비밀값 SEND_TOKEN)을 가진 요청만 받는다.
//
// 무료 요금제 한도 (2026-10 기준): 요청 10만/일, 호출당 외부 요청 50개, CPU 10ms, KV 쓰기 1천/일·목록 1천/일
//   → /send 는 한 번에 구독 BATCH 개씩만 처리하고 cursor 로 이어 간다. 구독 정보는 KV 메타데이터에 넣어 목록 한 번으로 읽는다.

const BATCH = 10;
const TTL = 60 * 60 * 24;                  // 푸시 서비스가 기기를 못 찾으면 하루 동안 보관 후 버린다
const SIDO = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종', '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주'];
// 브라우저 푸시 서비스 주소만 받는다 (임의 주소로 요청을 보내는 데 쓰이지 않게)
const PUSH_HOSTS = [/^fcm\.googleapis\.com$/, /^android\.googleapis\.com$/, /^updates\.push\.services\.mozilla\.com$/,
  /^web\.push\.apple\.com$/, /^[a-z0-9-]+\.push\.apple\.com$/, /^[a-z0-9-]+\.notify\.windows\.com$/];

const enc = new TextEncoder();
const b64u = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const unb64u = s => { s = s.replace(/-/g, '+').replace(/_/g, '/'); s += '='.repeat((4 - s.length % 4) % 4); return Uint8Array.from(atob(s), c => c.charCodeAt(0)); };
const cat = (...parts) => { const n = parts.reduce((a, p) => a + p.length, 0), out = new Uint8Array(n); let o = 0; for (const p of parts) { out.set(p, o); o += p.length; } return out; };

async function hmac(key, data) {
  const k = await crypto.subtle.importKey('raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', k, data));
}
async function sha256hex(s) {
  const h = new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(s)));
  return [...h].map(b => b.toString(16).padStart(2, '0')).join('');
}

// ---- VAPID (RFC 8292) ----
async function vapidKeys(env) {
  let jwk = await env.SUBS.get('vapid', 'json');
  if (!jwk) {
    const kp = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
    jwk = await crypto.subtle.exportKey('jwk', kp.privateKey);
    await env.SUBS.put('vapid', JSON.stringify(jwk));
  }
  const pub = cat(new Uint8Array([4]), unb64u(jwk.x), unb64u(jwk.y));
  return { jwk, pub: b64u(pub) };
}
async function vapidHeader(endpoint, keys, contact) {
  const aud = new URL(endpoint).origin;
  const head = b64u(enc.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const body = b64u(enc.encode(JSON.stringify({ aud, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: contact })));
  const key = await crypto.subtle.importKey('jwk', keys.jwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, enc.encode(head + '.' + body));   // r||s 64바이트 = JWS ES256 형식
  return `vapid t=${head}.${body}.${b64u(sig)}, k=${keys.pub}`;
}

// ---- 메시지 암호화 (RFC 8291, aes128gcm) ----
export async function encryptPayload(payload, p256dh, auth) {
  const uaPub = unb64u(p256dh), authSecret = unb64u(auth);
  const uaKey = await crypto.subtle.importKey('raw', uaPub, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const as = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);   // 메시지마다 새 키
  const asPub = new Uint8Array(await crypto.subtle.exportKey('raw', as.publicKey));
  const ecdh = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, as.privateKey, 256));
  const prkKey = await hmac(authSecret, ecdh);
  const ikm = await hmac(prkKey, cat(enc.encode('WebPush: info\0'), uaPub, asPub, new Uint8Array([1])));
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const prk = await hmac(salt, ikm);
  const cek = (await hmac(prk, cat(enc.encode('Content-Encoding: aes128gcm\0'), new Uint8Array([1])))).slice(0, 16);
  const nonce = (await hmac(prk, cat(enc.encode('Content-Encoding: nonce\0'), new Uint8Array([1])))).slice(0, 12);
  const key = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  const plain = cat(enc.encode(payload), new Uint8Array([2]));             // 마지막 레코드 구분자
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, key, plain));
  const rs = new Uint8Array([0, 0, 0x10, 0]);                                // 레코드 크기 4096
  return cat(salt, rs, new Uint8Array([asPub.length]), asPub, ct);
}

async function pushTo(sub, payload, keys, env) {
  const body = await encryptPayload(JSON.stringify(payload), sub.p, sub.a);
  const r = await fetch(sub.e, {
    method: 'POST',
    headers: { 'Content-Encoding': 'aes128gcm', 'Content-Type': 'application/octet-stream', TTL: String(TTL), Urgency: 'normal',
      Authorization: await vapidHeader(sub.e, keys, env.CONTACT || 'mailto:admin@cheongyakpass.kr') },
    body,
  });
  return r.status;
}

// ---- 구독자별로 이벤트 고르기·묶기 ----
// 이벤트: { kind: 'new'|'start'|'end', sido, good, name, line, url }
// 구독 설정: r(지역 목록, 비면 전체) · g(true 면 로또·고려 등급만) · m(true 면 접수 전날 알림도)
export function pick(events, pref) {
  return events.filter(ev => (!pref.r || !pref.r.length || pref.r.includes(ev.sido))
    && (!pref.g || ev.good) && (ev.kind === 'new' || pref.m));
}
const KIND_TITLE = { new: '새 공고', start: '내일 접수 시작', end: '내일 접수 마감' };
export function compose(evs) {
  if (evs.length === 1) {
    const ev = evs[0];
    return { title: `${KIND_TITLE[ev.kind]} · ${ev.name}`, body: ev.line, url: ev.url, tag: 'cp-' + ev.kind };
  }
  const n = k => evs.filter(e => e.kind === k).length;
  const head = ['new', 'start', 'end'].filter(k => n(k)).map(k => `${KIND_TITLE[k]} ${n(k)}`).join(' · ');
  const lines = evs.slice(0, 4).map(e => `${e.kind === 'new' ? '' : '[' + KIND_TITLE[e.kind] + '] '}${e.line}`);
  if (evs.length > 4) lines.push(`외 ${evs.length - 4}건`);
  return { title: `청약패스 · ${head}`, body: lines.join('\n'), url: '/', tag: 'cp-daily' };
}

// ---- HTTP ----
function cors(req, env) {
  const origin = req.headers.get('Origin') || '';
  const allow = (env.ALLOWED_ORIGINS || 'https://cheongyakpass.kr').split(',').map(s => s.trim());
  return allow.includes(origin) ? { 'Access-Control-Allow-Origin': origin, 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Max-Age': '86400', Vary: 'Origin' } : { Vary: 'Origin' };
}
const json = (obj, status, h) => new Response(JSON.stringify(obj), { status: status || 200, headers: { 'Content-Type': 'application/json; charset=utf-8', ...(h || {}) } });

function validSub(s, env) {
  if (!s || typeof s.endpoint !== 'string' || !s.keys || typeof s.keys.p256dh !== 'string' || typeof s.keys.auth !== 'string') return false;
  if (s.endpoint.length > 600 || s.keys.p256dh.length > 100 || s.keys.auth.length > 40) return false;
  let u; try { u = new URL(s.endpoint); } catch (e) { return false; }
  const devHosts = (env.DEV_PUSH_HOSTS || '').split(',').filter(Boolean);
  if (devHosts.includes(u.host)) return true;                                   // 로컬 검증용 (배포 설정에는 없음)
  return u.protocol === 'https:' && PUSH_HOSTS.some(re => re.test(u.hostname));
}
function cleanPrefs(p) {
  p = p || {};
  const r = Array.isArray(p.regions) ? [...new Set(p.regions.filter(x => SIDO.includes(x)))] : [];
  return { r, g: !!p.good, m: p.remind !== false };
}
async function authed(req, env) {
  const got = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!env.SEND_TOKEN || !got) return false;
  const [a, b] = await Promise.all([sha256hex(got), sha256hex(env.SEND_TOKEN)]);   // 길이·시간 차이를 줄이려고 해시끼리 비교
  return a === b;
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url), h = cors(req, env);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: h });
    try {
      if (url.pathname === '/health') return json({ ok: true }, 200, h);
      if (url.pathname === '/vapid' && req.method === 'GET') return json({ key: (await vapidKeys(env)).pub }, 200, { ...h, 'Cache-Control': 'max-age=3600' });

      if (url.pathname === '/subscribe' && req.method === 'POST') {
        if (!h['Access-Control-Allow-Origin']) return json({ error: 'origin' }, 403, h);
        const body = await req.json().catch(() => null);
        if (!body || !validSub(body.sub, env)) return json({ error: 'subscription' }, 400, h);
        const pref = cleanPrefs(body.prefs);
        const meta = { e: body.sub.endpoint, p: body.sub.keys.p256dh, a: body.sub.keys.auth, ...pref, t: new Date().toISOString().slice(0, 10) };
        if (enc.encode(JSON.stringify(meta)).length > 1000) return json({ error: 'too large' }, 400, h);   // KV 메타데이터 한도 1024바이트
        const id = 's:' + (await sha256hex(meta.e)).slice(0, 40);
        await env.SUBS.put(id, '', { metadata: meta });
        let test = null;
        if (body.test !== false) {
          const keys = await vapidKeys(env);
          test = await pushTo(meta, { title: '청약패스 알림이 켜졌어요', body: (pref.r.length ? pref.r.join('·') : '전국') + ' 새 공고' + (pref.m ? '와 접수 전날' : '') + ' 알림을 보내요.', url: '/#/alerts', tag: 'cp-hello' }, keys, env);
          if (test === 404 || test === 410) { await env.SUBS.delete(id); return json({ error: 'gone', status: test }, 410, h); }
        }
        return json({ ok: true, prefs: pref, test }, 200, h);
      }

      if (url.pathname === '/unsubscribe' && req.method === 'POST') {
        if (!h['Access-Control-Allow-Origin']) return json({ error: 'origin' }, 403, h);
        const body = await req.json().catch(() => null);
        if (!body || typeof body.endpoint !== 'string') return json({ error: 'endpoint' }, 400, h);
        await env.SUBS.delete('s:' + (await sha256hex(body.endpoint)).slice(0, 40));
        return json({ ok: true }, 200, h);
      }

      if (url.pathname === '/send' && req.method === 'POST') {
        if (!(await authed(req, env))) return json({ error: 'auth' }, 401);
        const body = await req.json().catch(() => null);
        const events = (body && Array.isArray(body.events)) ? body.events : null;
        if (!events) return json({ error: 'events' }, 400);
        const list = await env.SUBS.list({ prefix: 's:', limit: BATCH, cursor: body.cursor || undefined });
        const keys = await vapidKeys(env);
        const out = { seen: list.keys.length, sent: 0, none: 0, gone: 0, failed: 0, codes: {} };
        await Promise.all(list.keys.map(async k => {
          const sub = k.metadata;
          if (!sub || !sub.e) { out.failed++; return; }
          const evs = pick(events, sub);
          if (!evs.length) { out.none++; return; }
          if (body.dry) { out.sent++; return; }
          let st = 0;
          try { st = await pushTo(sub, compose(evs), keys, env); } catch (e) { st = 0; }
          out.codes[st] = (out.codes[st] || 0) + 1;
          if (st >= 200 && st < 300) out.sent++;
          else if (st === 404 || st === 410) { out.gone++; await env.SUBS.delete(k.name); }
          else out.failed++;
        }));
        out.next = list.list_complete ? null : list.cursor;
        return json(out);
      }
      return json({ error: 'not found' }, 404, h);
    } catch (e) {
      return json({ error: 'server', detail: String(e && e.message || e) }, 500, h);
    }
  },
};
