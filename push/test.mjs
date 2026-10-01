// 알림 서버(push/worker.js) 검증 — 기능: web_push
// 메모리 KV 와 가짜 푸시 서비스로 워커를 돌려 구독·발송·만료 정리·권한을 확인하고,
// 실제로 보낸 암호문과 서명을 push/test-out.json 에 남긴다. tests/test_webpush.py 가 이 파일을
// 워커와 따로 짠 RFC 8291 복호화·RFC 8292 서명 검증으로 풀어 본다 (같은 코드로 자기 검사하지 않게).
// 사용: node push/test.mjs
import { writeFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
if (!globalThis.crypto) globalThis.crypto = webcrypto;
const { default: worker, pick, compose } = await import('./worker.js');

const assert = (c, m) => { if (!c) { console.error('실패: ' + m); process.exitCode = 1; } else console.log('통과: ' + m); };
const b64u = buf => Buffer.from(buf).toString('base64url');

// ---- 메모리 KV (list 는 이름순·limit·cursor·metadata) ----
function memKV() {
  const m = new Map();
  return {
    m,
    async get(k, t) { const v = m.get(k); return v == null ? null : t === 'json' ? JSON.parse(v.value) : v.value; },
    async put(k, value, o) { m.set(k, { value, metadata: o && o.metadata }); },
    async delete(k) { m.delete(k); },
    async list({ prefix = '', limit = 1000, cursor }) {
      const names = [...m.keys()].filter(k => k.startsWith(prefix)).sort();
      const rest = cursor ? names.filter(n => n > cursor) : names, page = rest.slice(0, limit);   // 이어 받기는 마지막 이름 다음부터 (중간 삭제에 밀리지 않게)
      const done = rest.length <= limit;
      return { keys: page.map(n => ({ name: n, metadata: m.get(n).metadata })), list_complete: done, cursor: done ? undefined : page[page.length - 1] };
    },
  };
}
// ---- 가짜 푸시 서비스: 보낸 요청을 모으고, 주소에 따라 상태 코드를 돌려준다 ----
const sent = [];
globalThis.fetch = async (url, init) => {
  sent.push({ url, headers: init.headers, body: Buffer.from(init.body).toString('base64') });
  return new Response(null, { status: url.includes('/gone') ? 410 : url.includes('/fail') ? 500 : 201 });
};
const env = { SUBS: memKV(), SEND_TOKEN: 'test-token', ALLOWED_ORIGINS: 'https://cheongyakpass.kr', CONTACT: 'mailto:test@example.com' };
const call = (path, { method = 'GET', body, origin = 'https://cheongyakpass.kr', token } = {}) => worker.fetch(new Request('https://push.test' + path, {
  method, body: body ? JSON.stringify(body) : undefined,
  headers: { 'Content-Type': 'application/json', ...(origin ? { Origin: origin } : {}), ...(token ? { Authorization: 'Bearer ' + token } : {}) },
}), env);

// 브라우저 쪽 구독 키 (받는 쪽 개인 키는 검증 파일에 넣어 파이썬이 복호화한다)
async function browserSub(endpoint) {
  const kp = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const pub = new Uint8Array(await crypto.subtle.exportKey('raw', kp.publicKey));
  const jwk = await crypto.subtle.exportKey('jwk', kp.privateKey);
  const auth = crypto.getRandomValues(new Uint8Array(16));
  return { sub: { endpoint, keys: { p256dh: b64u(pub), auth: b64u(auth) } }, priv: jwk.d };
}

const out = { vapid: null, pushes: [] };
// 1. VAPID 공개 키: 처음 만들고, 두 번째도 같은 키
const v1 = await (await call('/vapid')).json(), v2 = await (await call('/vapid')).json();
out.vapid = v1.key;
assert(v1.key && v1.key === v2.key && Buffer.from(v1.key, 'base64url').length === 65, 'VAPID 공개 키 65바이트, 다시 불러도 같음');

// 2. 구독: 허용 출처만, 푸시 서비스 주소만
const A = await browserSub('https://fcm.googleapis.com/fcm/send/aaa');
let r = await call('/subscribe', { method: 'POST', body: { sub: A.sub, prefs: { regions: ['서울', '경기', '없는곳'], good: false, remind: true } } });
let j = await r.json();
assert(r.status === 200 && j.ok && j.test === 201 && JSON.stringify(j.prefs.r) === '["서울","경기"]', '구독 저장 + 확인 알림 1통 (없는 지역 이름은 버림)');
assert(sent.length === 1 && sent[0].url === A.sub.endpoint, '확인 알림을 그 구독 주소로 보냄');
out.pushes.push({ ...sent[0], priv: A.priv, p256dh: A.sub.keys.p256dh, auth: A.sub.keys.auth, expect: { title: '청약패스 알림이 켜졌어요' } });
r = await call('/subscribe', { method: 'POST', origin: 'https://evil.example', body: { sub: A.sub } });
assert(r.status === 403, '다른 사이트에서 온 구독 요청은 거절');
const bad = await browserSub('https://evil.example/collect');
r = await call('/subscribe', { method: 'POST', body: { sub: bad.sub } });
assert(r.status === 400, '푸시 서비스가 아닌 주소는 거절');
r = await call('/subscribe', { method: 'POST', body: { sub: { endpoint: 'https://fcm.googleapis.com/x' } } });
assert(r.status === 400, '키가 없는 구독은 거절');
const G = await browserSub('https://updates.push.services.mozilla.com/wpush/v2/gone');
r = await call('/subscribe', { method: 'POST', body: { sub: G.sub, prefs: {} } });
assert(r.status === 410 && ![...env.SUBS.m.keys()].some(k => env.SUBS.m.get(k).metadata?.e === G.sub.endpoint), '확인 알림이 410 이면 저장하지 않음');

// 같은 주소로 다시 구독하면 설정만 바뀜 (확인 알림 없이)
const before = sent.length;
r = await call('/subscribe', { method: 'POST', body: { sub: A.sub, prefs: { regions: ['서울'], good: false, remind: true }, test: false } });
assert(r.status === 200 && sent.length === before && [...env.SUBS.m.keys()].filter(k => k.startsWith('s:')).length === 1, '설정 바꾸기는 덮어쓰기, 확인 알림 없음');

// 3. 여러 구독자
const B = await browserSub('https://web.push.apple.com/bbb');
await call('/subscribe', { method: 'POST', body: { sub: B.sub, prefs: { regions: [], good: true, remind: false }, test: false } });
const C = await browserSub('https://fcm.googleapis.com/fcm/send/gone');
await call('/subscribe', { method: 'POST', body: { sub: C.sub, prefs: { regions: ['부산'] }, test: false } });
const D = await browserSub('https://fcm.googleapis.com/fcm/send/ddd');
await call('/subscribe', { method: 'POST', body: { sub: D.sub, prefs: { regions: ['제주'] }, test: false } });
for (let i = 0; i < 12; i++) {   // 한 번에 BATCH(10)개라 이어 받기를 확인하려고 더 넣는다
  const X = await browserSub('https://fcm.googleapis.com/fcm/send/x' + i);
  await call('/subscribe', { method: 'POST', body: { sub: X.sub, prefs: { regions: ['대구'] }, test: false } });
}

const events = [
  { kind: 'new', sido: '서울', good: true, name: '서울 A단지', line: '[로또] 서울 A단지 (강동구) · 접수 2026-10-08', url: '/#/detail/1-084A' },
  { kind: 'new', sido: '경기', good: false, name: '경기 B단지', line: '경기 B단지 (성남시) · 접수 2026-10-09', url: '/#/detail/2-059A' },
  { kind: 'start', sido: '서울', good: false, name: '서울 C단지', line: '서울 C단지 (마포구) · 접수 2026-10-02', url: '/#/detail/3-084A' },
  { kind: 'new', sido: '부산', good: false, name: '부산 D단지', line: '부산 D단지 · 접수 2026-10-10', url: '/#/detail/4-084A' },
  { kind: 'new', sido: '대구', good: false, name: '대구 E단지', line: '대구 E단지 · 접수 2026-10-10', url: '/#/detail/5-084A' },
];
// 고르기·묶기 규칙
assert(pick(events, { r: ['서울'], g: false, m: true }).length === 2, '서울·전날 알림 켬 → 서울 새 공고 + 내일 접수 시작');
assert(pick(events, { r: ['서울'], g: false, m: false }).length === 1, '전날 알림 끔 → 새 공고만');
assert(pick(events, { r: [], g: true, m: true }).map(e => e.name).join() === '서울 A단지', '전국·로또·고려만 → 등급 좋은 공고만');
assert(pick(events, { r: ['제주'], g: false, m: true }).length === 0, '맞는 공고가 없으면 보내지 않음');
const one = compose([events[0]]), two = compose(pick(events, { r: ['서울'], g: false, m: true }));
assert(one.title === '새 공고 · 서울 A단지' && one.url === '/#/detail/1-084A', '한 건이면 공고 이름·상세 화면 주소');
assert(two.title === '청약패스 · 새 공고 1 · 내일 접수 시작 1' && two.body.split('\n').length === 2 && two.url === '/', '여러 건이면 한 통으로 묶음');
const many = compose(Array.from({ length: 6 }, (_, i) => ({ ...events[1], name: 'n' + i })));
assert(many.body.split('\n').length === 5 && many.body.endsWith('외 2건'), '5건 이상이면 4줄 + 외 n건');

// 4. 발송: 토큰 없으면 거절
r = await call('/send', { method: 'POST', body: { events } });
assert(r.status === 401, '토큰 없는 발송은 거절');
r = await call('/send', { method: 'POST', token: 'wrong', body: { events } });
assert(r.status === 401, '틀린 토큰은 거절');
// 미리 보기(dry): 보내지 않고 셈만
const before2 = sent.length;
let cursor = null, tot = { seen: 0, sent: 0, none: 0, gone: 0, failed: 0 }, calls = 0;
do {
  j = await (await call('/send', { method: 'POST', token: 'test-token', body: { events, cursor, dry: true } })).json();
  for (const k in tot) tot[k] += j[k]; cursor = j.next; calls++;
} while (cursor);
assert(sent.length === before2 && tot.seen === 16 && calls === 2, `미리 보기는 보내지 않음, 16명을 ${calls}번에 나눠 셈`);
// 실제 발송
cursor = null; tot = { seen: 0, sent: 0, none: 0, gone: 0, failed: 0 };
do {
  j = await (await call('/send', { method: 'POST', token: 'test-token', body: { events, cursor } })).json();
  for (const k in tot) tot[k] += j[k]; cursor = j.next;
} while (cursor);
const subsLeft = [...env.SUBS.m.keys()].filter(k => k.startsWith('s:')).length;
console.log(JSON.stringify(tot));
assert(tot.sent === 14 && tot.gone === 1 && tot.none === 1 && subsLeft === 15, `보냄 14(서울 1·전국등급 1·대구 12) · 만료 1 삭제 · 대상 아님 1(제주) → 남은 구독 ${subsLeft}`);
const toA = sent.filter(s => s.url === A.sub.endpoint).pop(), toB = sent.filter(s => s.url === B.sub.endpoint).pop();
out.pushes.push({ ...toA, priv: A.priv, p256dh: A.sub.keys.p256dh, auth: A.sub.keys.auth, expect: { title: two.title, body: two.body, url: '/' } });
out.pushes.push({ ...toB, priv: B.priv, p256dh: B.sub.keys.p256dh, auth: B.sub.keys.auth, expect: { title: one.title, url: '/#/detail/1-084A' } });
assert(toA.headers['Content-Encoding'] === 'aes128gcm' && toA.headers.TTL === '86400' && /^vapid t=.+, k=/.test(toA.headers.Authorization), '푸시 요청 헤더 (aes128gcm·TTL·VAPID)');

// 5. 구독 해지
r = await call('/unsubscribe', { method: 'POST', body: { endpoint: A.sub.endpoint } });
assert(r.status === 200 && ![...env.SUBS.m.values()].some(v => v.metadata?.e === A.sub.endpoint), '구독 해지하면 바로 지움');
// 6. CORS 사전 요청
r = await call('/subscribe', { method: 'OPTIONS' });
assert(r.status === 204 && r.headers.get('Access-Control-Allow-Origin') === 'https://cheongyakpass.kr', 'CORS 는 청약패스 주소만 허용');

writeFileSync(new URL('./test-out.json', import.meta.url), JSON.stringify(out, null, 1));
console.log(process.exitCode ? '알림 서버 검증 실패' : '알림 서버 검증 모두 통과 · 복호화 검증용 ' + out.pushes.length + '통 저장');
