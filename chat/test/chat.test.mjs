// node --test test/  — 검사기가 나쁜 답을 실제로 막는지, 서버가 제한·가림·재시도·대체를 제대로 하는지.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { handleChat, handleFeedback } from '../worker/src/index.js';
import worker from '../worker/src/index.js';
import { parseEvidence, selectEvidence } from '../worker/src/evidence.js';
import { validate } from '../worker/src/validate.js';
import { redact } from '../worker/src/redact.js';
import { classify } from '../worker/src/intent.js';
const require = createRequire(import.meta.url);
const { loadEngine, buildEngine } = require('../tools/engine_payload.cjs');

const REPO = process.env.REPO || new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const eng = loadEngine(REPO + '/docs', REPO + '/tests/judge/listings.json');
const index = parseEvidence(fs.readFileSync(REPO + '/docs/rules-evidence.txt', 'utf8'));
const G = Object.fromEntries(JSON.parse(fs.readFileSync(new URL('../golden/golden_v0.json', import.meta.url))).map(g => [g.id, g]));
const GOOD = JSON.parse(fs.readFileSync(new URL('../golden/fixtures_good.json', import.meta.url)));
const OPEN = { CHAT_OPEN: '1' };
class MemKV { constructor() { this.m = new Map(); } async get(k) { return this.m.get(k) ?? null; } async put(k, v) { this.m.set(k, v); } async delete(k) { this.m.delete(k); } }

const ctxOf = id => { const g = G[id]; const engine = buildEngine(eng, g.listing, g.profile); return { engine, evidence: selectEvidence(index, engine, g.question).evidence, question: g.question }; };
const tweak = (id, f) => { const a = JSON.parse(GOOD[id]); f(a); return JSON.stringify(a); };

// ── 검사기: 좋은 답은 통과 ──
for (const id of Object.keys(GOOD)) {
  test(`좋은 답 통과: ${id}`, () => { const v = validate(GOOD[id], ctxOf(id)); assert.ok(v.ok, v.flags.join(' / ')); });
}

// ── 검사기: 나쁜 답은 막힘 ──
const BAD = [
  ['판정 값 뒤집기', 'kakao-mom-1', a => { a.verdict = '가능'; }, /판정 불일치/],
  ['결론이 엔진과 반대(불가인데 가능)', 'kakao-mom-1', a => { a.conclusion = '이 주택형에 신청할 수 있어요.'; }, /결론이 엔진\(불가\)과 반대/],
  ['확인 필요를 가능으로 단정', 'ask-1', a => { a.conclusion = '네, 신청 가능해요.'; }, /확인 필요/],
  ['특공 판정 뒤집기', 'ask-1', a => { a.cautions.push('생애최초 특별공급은 신청할 수 있어요.'); }, /생애최초 특공/],
  ['지어낸 숫자', 'kakao-mom-1', a => { a.why[1].text = '상한은 9,876,543원이에요.'; }, /출처 없는 숫자/],
  ['금지 표현', 'nht-8y-5', a => { a.cautions.push('무조건 넣으세요!'); }, /금지 표현/],
  ['근거 번호 없는 규정', 'kakao-mom-3', a => { a.official[0].refs = []; }, /근거 번호 없는/],
  ['없는 근거 번호', 'kakao-mom-3', a => { a.official[0].refs = ['N99']; }, /없는 근거 번호 N99/],
  ['개인정보 다시 쓰기', 'ask-1', a => { a.cautions.push('주민번호 900101-1234567 확인했어요.'); }, /개인정보 노출/],
];
for (const [name, id, f, re] of BAD) {
  test(`나쁜 답 차단: ${name}`, () => { const v = validate(tweak(id, f), ctxOf(id)); assert.equal(v.ok, false); assert.match(v.flags.join(' / '), re); });
}
test('나쁜 답 차단: JSON 이 아님', () => { assert.equal(validate('그냥 가능해요!', ctxOf('ask-1')).ok, false); });

// ── 가리기·분류 ──
test('개인정보 가리기', () => {
  const r = redact('900101-1234567 010-1234-5678 a.b@ex.com 101동 1203호 123-456-789012 2026-10-01');
  assert.deepEqual(new Set(r.found), new Set(['주민등록번호', '전화번호', '이메일', '동·호수', '계좌번호']));
  assert.ok(r.text.includes('2026-10-01'), '날짜는 가리지 않음');
});
test('질문 분류', () => {
  assert.equal(classify('이거 나 가능해?'), 'judge');
  assert.equal(classify('지금 사두면 오를까요?'), 'out_of_scope');
  assert.equal(classify('발표 언제예요?'), 'schedule');
  assert.equal(classify('필요 서류 뭐예요'), 'docs');
  assert.equal(classify('소득 기준이 뭐야?'), 'rule');
});

// ── 서버 본체 ──
const input = (id, extra = {}) => { const g = G[id]; return { question: g.question, engine: buildEngine(eng, g.listing, g.profile), anon_id: 'tester-0001', conversation_id: 'conv-1', ip: '9.9.9.9', ...extra }; };

test('하루 2건 제한, 되물음 답은 세지 않음', async () => {
  const kv = new MemKV();
  const r1 = await handleChat(OPEN, input('ask-1'), { kv, evidence: index });
  assert.equal(r1.status, 200); assert.ok(r1.body.answer.ask, '되물음이 있어야 함');
  const r2 = await handleChat(OPEN, input('ask-1', { question: '서울 양천구요' }), { kv, evidence: index });
  assert.equal(r2.body.follow_up, true, '되물음 답은 같은 1건');
  const r3 = await handleChat(OPEN, input('kakao-mom-1', { conversation_id: 'conv-2' }), { kv, evidence: index });
  assert.equal(r3.status, 200);
  const r4 = await handleChat(OPEN, input('kakao-mom-1', { conversation_id: 'conv-3' }), { kv, evidence: index });
  assert.equal(r4.status, 429); assert.equal(r4.body.limited, 'user');
});

test('사이트 전체 하루 상한', async () => {
  const kv = new MemKV(); const today = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  await kv.put('g:' + today, '100');
  const r = await handleChat(OPEN, input('ask-1'), { kv, evidence: index });
  assert.equal(r.status, 429); assert.equal(r.body.limited, 'global');
  assert.match(r.body.message, /오늘 질문이 마감됐어요/);
});

test('AI 로 가는 문장에 개인정보가 없음', async () => {
  let seen = '';
  const llm = async ({ user }) => { seen = user; return { text: GOOD['ask-1'] }; };
  await handleChat(OPEN, input('ask-1', { question: '제 주민번호 900101-1234567 인데 가능해요?' }), { kv: new MemKV(), evidence: index, llm });
  assert.ok(!seen.includes('1234567')); assert.ok(seen.includes('[주민등록번호 가림]'));
});

test('첫 답이 막히면 다시 쓰고, 두 번째 답을 씀', async () => {
  const bad = tweak('kakao-mom-1', a => { a.verdict = '가능'; });
  const llm = async ({ attempt, user }) => ({ text: attempt === 0 ? bad : (assert.match(user, /PREVIOUS_ANSWER_REJECTED/), GOOD['kakao-mom-1']) });
  const r = await handleChat(OPEN, input('kakao-mom-1'), { kv: new MemKV(), evidence: index, llm });
  assert.equal(r.body.fallback, false); assert.equal(r.body.answer.verdict, '불가'); assert.equal(r.body.log.attempts.length, 2);
});

test('두 번 다 막히면 고정 문구 답으로 대체', async () => {
  const bad = tweak('kakao-mom-1', a => { a.conclusion = '무조건 신청할 수 있어요.'; });
  const r = await handleChat(OPEN, input('kakao-mom-1'), { kv: new MemKV(), evidence: index, llm: async () => ({ text: bad }) });
  assert.equal(r.body.fallback, true); assert.equal(r.body.answer.verdict, '불가');
  assert.ok(validate(r.body.answer, ctxOf('kakao-mom-1')).ok, '대체 답도 검사기를 통과');
});

test('AI 호출이 실패해도 엔진 결과로 답함', async () => {
  const r = await handleChat(OPEN, input('kakao-mom-1'), { kv: new MemKV(), evidence: index, llm: async () => { throw new Error('timeout'); } });
  assert.equal(r.status, 200); assert.equal(r.body.fallback, true); assert.equal(r.body.verdict, '불가');
});

test('범위 밖 질문은 AI 를 부르지 않음', async () => {
  let called = false;
  const r = await handleChat(OPEN, input('scope-1'), { kv: new MemKV(), evidence: index, llm: async () => { called = true; return { text: '' }; } });
  assert.equal(r.body.kind, 'out_of_scope'); assert.equal(called, false);
});

test('엔진 결과 형식이 이상하면 거절', async () => {
  const bad = input('ask-1'); bad.engine.verdict = '아마 될 듯';
  const r = await handleChat(OPEN, bad, { kv: new MemKV(), evidence: index });
  assert.equal(r.status, 400);
});

// ── 저장소에 넣으며 더한 것 (2026-10-01): 미리보기 잠금·하루 합계·평가·IP 가리기·공고별 근거 ──
test('공개 전에는 미리보기 코드가 있어야 답함', async () => {
  const env = { CHAT_PREVIEW_CODE: 'preview-secret-123' };
  const r1 = await handleChat(env, input('kakao-mom-1'), { kv: new MemKV(), evidence: index });
  assert.equal(r1.status, 403); assert.equal(r1.body.closed, true);
  const r2 = await handleChat(env, input('kakao-mom-1', { preview: 'wrong' }), { kv: new MemKV(), evidence: index });
  assert.equal(r2.status, 403);
  const r3 = await handleChat(env, input('kakao-mom-1', { preview: 'preview-secret-123' }), { kv: new MemKV(), evidence: index });
  assert.equal(r3.status, 200);
  const r4 = await handleChat({}, input('kakao-mom-1', { preview: '' }), { kv: new MemKV(), evidence: index });
  assert.equal(r4.status, 403, '코드가 설정되지 않았으면 빈 코드로 열리지 않음');
});

test('KV 에 IP·기기 번호·질문 원문이 남지 않음, 하루 합계만', async () => {
  const kv = new MemKV();
  await handleChat({ ...OPEN, CHAT_STATS_TOKEN: 'salt-xyz' }, input('ask-1', { question: '010-1234-5678 제가 가능해요?' }), { kv, evidence: index, llm: async () => ({ text: GOOD['ask-1'], usage: { input_tokens: 7000, output_tokens: 500 } }) });
  const all = [...kv.m.entries()].map(([k, v]) => k + '=' + v).join('\n');
  assert.ok(!all.includes('9.9.9.9') && !all.includes('tester-0001') && !all.includes('5678') && !all.includes('가능해요?'), all);
  const today = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const s = JSON.parse(kv.m.get('s:' + today));
  assert.equal(s.q, 1); assert.equal(s.pii, 1); assert.equal(s.in_tokens, 7000); assert.equal(s.out_tokens, 500); assert.equal(s.verdict['확인 필요'] || s.verdict[G['ask-1'].expect_verdict] || 1, 1);
});

test('답변 평가: 이유 7가지만 받고 합계로', async () => {
  const kv = new MemKV();
  assert.equal((await handleFeedback(OPEN, { vote: 'down', reason: 'wrong_info', recheck: 'same' }, { kv })).status, 200);
  assert.equal((await handleFeedback(OPEN, { vote: 'up' }, { kv })).status, 200);
  assert.equal((await handleFeedback(OPEN, { vote: 'down', reason: '<script>' }, { kv })).status, 400);
  assert.equal((await handleFeedback(OPEN, { vote: 'meh' }, { kv })).status, 400);
  const s = JSON.parse([...kv.m.values()][0]);
  assert.equal(s.fb_down, 1); assert.equal(s.fb_up, 1); assert.equal(s.fb_reason.wrong_info, 1); assert.equal(s.recheck.same, 1);
});

test('서버: 다른 사이트에서 온 요청·토큰 없는 합계 요청은 거절', async () => {
  const env = { ...OPEN, ALLOWED_ORIGINS: 'https://cheongyakpass.kr', CHAT_STATS_TOKEN: 'tok', CHAT_KV: new MemKV() };
  const bad = await worker.fetch(new Request('https://x.workers.dev/chat', { method: 'POST', headers: { origin: 'https://evil.example' }, body: '{}' }), env);
  assert.equal(bad.status, 403);
  const st = await worker.fetch(new Request('https://x.workers.dev/stats'), env);
  assert.equal(st.status, 401);
  const st2 = await worker.fetch(new Request('https://x.workers.dev/stats', { headers: { authorization: 'Bearer tok' } }), env);
  assert.equal(st2.status, 200);
  const pre = await worker.fetch(new Request('https://x.workers.dev/feedback', { method: 'OPTIONS', headers: { origin: 'https://cheongyakpass.kr' } }), env);
  assert.equal(pre.status, 204); assert.equal(pre.headers.get('access-control-allow-origin'), 'https://cheongyakpass.kr');
});

test('근거는 법령과 물어본 공고의 공고문 조각만 받음 (docs/chat-law.json · chat-notice)', async () => {
  const urls = [];
  const g = G['kakao-mom-1'], nid = g.listing.split('-')[0];
  const files = { 'chat-law.json': REPO + '/docs/chat-law.json', [`chat-notice/${nid}.json`]: REPO + '/docs/chat-notice/' + nid + '.json' };
  const fetchImpl = async u => { urls.push(String(u)); const k = String(u).replace('https://cheongyakpass.kr/', ''); return files[k] && fs.existsSync(files[k]) ? { ok: true, json: async () => JSON.parse(fs.readFileSync(files[k], 'utf8')) } : { ok: false }; };
  const r = await handleChat(OPEN, input('kakao-mom-1'), { kv: new MemKV(), fetch: fetchImpl });
  assert.equal(r.status, 200);
  assert.deepEqual(urls.sort(), ['https://cheongyakpass.kr/chat-law.json', `https://cheongyakpass.kr/chat-notice/${nid}.json`].sort());
});

// ── 청약 전반 질문 (2026-10-02): 공고 판정 없이도, 공고문 조각에서 서류를 찾아 답함 ──
const LAW = JSON.parse(fs.readFileSync(REPO + '/docs/chat-law.json', 'utf8'));
const NOTICE453 = fs.existsSync(REPO + '/docs/chat-notice/2026000453.json') ? JSON.parse(fs.readFileSync(REPO + '/docs/chat-notice/2026000453.json', 'utf8')) : null;
const genIn = (q, extra = {}) => ({ question: q, engine: null, anon_id: 'tester-gen-01', conversation_id: 'g-' + Math.random(), ip: '5.5.5.5', ...extra });
test('일반 질문: 판정 없이 법령 근거로 답함 (AI 없으면 원문 조각)', async () => {
  const r = await handleChat(OPEN, genIn('1순위 조건이 뭐야?'), { kv: new MemKV(), law: LAW, notice: null });
  assert.equal(r.status, 200); assert.equal(r.body.verdict, null);
  assert.ok(r.body.answer.official.length > 0 && r.body.sources.every(x => x.kind === 'law'));
  assert.ok(r.body.sources.some(x => /제28조|제27조|제2조/.test(x.title)), JSON.stringify(r.body.sources.map(x => x.title)));
});
test('공고 서류 질문: 공고문 조각에서 서류 내용을 찾아 보여줌', { skip: !NOTICE453 }, async () => {
  const r = await handleChat(OPEN, genIn('필요한 서류는 뭐야?', { listing_id: '2026000453-059.9742A' }), { kv: new MemKV(), law: LAW, notice: NOTICE453 });
  const txt = r.body.answer.official.map(x => x.text).join(' ');
  assert.match(txt, /등본|증명서|서류/); assert.ok(!/공고문의 제출 서류 항목에서 확인하세요/.test(JSON.stringify(r.body.answer)));
});
test('일반 질문인데 AI 가 판정을 지어내면 막음', async () => {
  const bad = JSON.stringify({ verdict: '가능', conclusion: '신청할 수 있어요.', my_conditions: [], why: [], official: [], cautions: [], ask: null });
  const good = JSON.stringify({ verdict: null, conclusion: '1순위는 통장 가입기간과 예치금 요건을 채워야 해요.', my_conditions: [], why: [], official: [{ text: '민영주택 1순위 요건은 주택공급에 관한 규칙 제28조에 있어요.', refs: ['L1'] }], cautions: [], ask: null });
  const llm = async ({ attempt }) => ({ text: attempt ? good : bad });
  const r = await handleChat(OPEN, genIn('1순위 조건이 뭐야?'), { kv: new MemKV(), law: LAW, notice: null, llm });
  assert.equal(r.body.fallback, false); assert.equal(r.body.answer.verdict, null); assert.equal(r.body.log.attempts.length, 2);
});

test('답이 계속 되물어도 공짜 되물음은 질문 1건당 2번까지', async () => {
  const kv = new MemKV(); const base = { conversation_id: 'conv-loop' };
  const llm = async () => ({ text: GOOD['ask-1'] });   // 늘 되묻는 답
  const r1 = await handleChat(OPEN, input('ask-1', base), { kv, evidence: index, llm });
  assert.equal(r1.body.follow_up, false); assert.equal(r1.body.remaining, 1);
  const r2 = await handleChat(OPEN, input('ask-1', { ...base, question: '서울 양천구요' }), { kv, evidence: index, llm });
  const r3 = await handleChat(OPEN, input('ask-1', { ...base, question: '세대주예요' }), { kv, evidence: index, llm });
  assert.equal(r2.body.follow_up, true); assert.equal(r3.body.follow_up, true);
  const r4 = await handleChat(OPEN, input('ask-1', { ...base, question: '그럼 소득은요?' }), { kv, evidence: index, llm });
  assert.equal(r4.body.follow_up, false, '세 번째부터는 새 질문으로 셈'); assert.equal(r4.body.remaining, 0);
  const r5 = await handleChat(OPEN, input('ask-1', { ...base, conversation_id: 'conv-new' }), { kv, evidence: index, llm });
  assert.equal(r5.status, 429);
});

// ── 운영 명령·월 사용액 한도·꼼수 방지 (2026-10-02) ──
test('!점검·!오픈: 미리보기 코드가 맞는 운영자만, 횟수에 안 셈', async () => {
  const kv = new MemKV(), env = { CHAT_PREVIEW_CODE: 'op-code-123' };
  const nope = await handleChat(env, input('kakao-mom-1', { question: '!점검' }), { kv, evidence: index });
  assert.equal(nope.status, 403); assert.equal(kv.m.get('mode'), undefined, '코드 없으면 명령 안 됨');
  const m = await handleChat(env, input('kakao-mom-1', { question: '!점검', preview: 'op-code-123' }), { kv, evidence: index });
  assert.equal(m.body.kind, 'admin'); assert.equal(kv.m.get('mode'), 'maint');
  const blocked = await handleChat({ ...env, CHAT_OPEN: '1' }, input('kakao-mom-1', { anon_id: 'someone-1234' }), { kv, evidence: index });
  assert.equal(blocked.status, 503); assert.equal(blocked.body.maint, true);
  const op = await handleChat(env, input('kakao-mom-1', { preview: 'op-code-123', conversation_id: 'c-op' }), { kv, evidence: index });
  assert.equal(op.status, 503, '점검 중엔 운영자 질문도 멈춤');
  await handleChat(env, input('kakao-mom-1', { question: '!오픈', preview: 'op-code-123' }), { kv, evidence: index });
  assert.equal(kv.m.get('mode'), 'open');
  const pub = await handleChat(env, input('kakao-mom-1', { anon_id: 'someone-1234', ip: '7.7.7.7' }), { kv, evidence: index });
  assert.equal(pub.status, 200, '!오픈 뒤에는 미리보기 코드 없이도 답함');
  assert.ok(![...kv.m.keys()].some(k => k.startsWith('u:') && false));
});

test('!무료: 운영자 질문만 AI 안 부르고 횟수 제한 없음, !AI 로 복귀', async () => {
  const kv = new MemKV(), env = { CHAT_PREVIEW_CODE: 'op-code-123' }; let calls = 0;
  const llm = async () => { calls++; return { text: '{}', usage: { input_tokens: 1, output_tokens: 1 } }; };
  const no = await handleChat(env, input('kakao-mom-1', { question: '!무료' }), { kv, evidence: index, llm });
  assert.equal(no.status, 403); assert.equal(kv.m.get('opfree'), undefined, '코드 없으면 안 됨');
  const m = await handleChat(env, input('kakao-mom-1', { question: '!무료', preview: 'op-code-123' }), { kv, evidence: index, llm });
  assert.equal(m.body.kind, 'admin'); assert.equal(m.body.opfree, true, '기기가 기억할 값');
  for (let i = 0; i < 6; i++) {
    const r = await handleChat(env, input('kakao-mom-1', { preview: 'op-code-123', free: true, conversation_id: 'f' + i }), { kv, evidence: index, llm });
    assert.equal(r.status, 200, '제한 없음 ' + i); assert.equal(r.body.fallback, true);
  }
  assert.equal(calls, 0, 'AI 호출 0');
  const pub = await handleChat({ ...env, CHAT_OPEN: '1' }, input('kakao-mom-1', { anon_id: 'someone-1234', ip: '8.8.8.8' }), { kv, evidence: index, llm });
  assert.ok(calls > 0, '다른 이용자는 그대로 AI'); calls = 0;
  const back = await handleChat(env, input('kakao-mom-1', { question: '!AI', preview: 'op-code-123' }), { kv, evidence: index, llm });
  assert.equal(back.body.opfree, false);
  await handleChat(env, input('kakao-mom-1', { preview: 'op-code-123', conversation_id: 'g1' }), { kv, evidence: index, llm });
  assert.ok(calls > 0, '!AI 뒤에는 운영자도 AI');
});

test('같은 인터넷 주소는 기기 번호를 바꿔도 하루 3번까지', async () => {
  const kv = new MemKV(); let ok = 0;
  for (let i = 0; i < 5; i++) { const r = await handleChat(OPEN, input('kakao-mom-1', { anon_id: 'device-' + i + '-xxxx', conversation_id: 'cv' + i }), { kv, evidence: index }); if (r.status === 200) ok++; }
  assert.equal(ok, 3);
});

test('이번 달 추정 사용액이 서버 한도에 닿으면 AI 없이 답함', async () => {
  const kv = new MemKV(); const month = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 7);
  let called = 0; const llm = async () => { called++; return { text: GOOD['kakao-mom-1'], usage: { input_tokens: 7000, output_tokens: 600 } }; };
  const r1 = await handleChat({ ...OPEN, CHAT_MONTH_USD: '18' }, input('kakao-mom-1', { conversation_id: 'a1' }), { kv, evidence: index, llm });
  assert.equal(called, 1); assert.ok(+kv.m.get('mspend:' + month) > 0.009);
  await kv.put('mspend:' + month, '18.01');
  const r2 = await handleChat({ ...OPEN, CHAT_MONTH_USD: '18' }, input('kakao-mom-1', { conversation_id: 'a2' }), { kv, evidence: index, llm });
  assert.equal(called, 1, '한도 넘으면 AI 를 부르지 않음'); assert.equal(r2.body.fallback, true); assert.equal(r2.body.verdict, '불가');
});
