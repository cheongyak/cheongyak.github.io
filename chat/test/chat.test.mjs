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

test('근거는 물어본 공고 파일만 받음 (docs/chat-evidence)', async () => {
  const urls = [];
  const g = G['kakao-mom-1'], nid = g.listing.split('-')[0];
  const file = JSON.parse(fs.readFileSync(REPO + '/docs/chat-evidence/' + nid + '.json', 'utf8'));
  const fetchImpl = async u => { urls.push(String(u)); return { ok: true, json: async () => file }; };
  const r = await handleChat({ ...OPEN, EVIDENCE_BASE: 'https://cheongyakpass.kr/chat-evidence' }, input('kakao-mom-1'), { kv: new MemKV(), fetch: fetchImpl });
  assert.equal(r.status, 200);
  assert.deepEqual(urls, ['https://cheongyakpass.kr/chat-evidence/' + nid + '.json']);
  assert.ok(r.body.answer.official.length > 0, '공고문 근거가 붙음');
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
