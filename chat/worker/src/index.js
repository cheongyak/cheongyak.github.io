// 청약패스 청약봇 서버 (Cloudflare Worker, 시험용). 판정은 하지 않는다.
// 브라우저가 판정 엔진 결과(engine)와 질문을 보내면, 근거를 붙여 Claude 에게 '설명'만 맡기고 검사기를 통과한 답만 돌려준다.
import { redact } from './redact.js';
import { classify, OUT_OF_SCOPE_TEXT } from './intent.js';
import { selectEvidence } from './evidence.js';
import { SYSTEM, PROMPT_VERSION, buildUserMessage } from './prompt.js';
import { validate } from './validate.js';
import { fallbackAnswer, fallbackGeneral } from './fallback.js';
import { selectGeneral } from './retrieve.js';
import { checkLimit, markConversation, LIMIT_TEXT } from './limits.js';
import { callClaude, MODEL } from './llm.js';
import { bump, readStats, FEEDBACK_REASONS } from './stats.js';

const VERDICTS = ['가능', '불가', '확인 필요', '2순위만'];
// 청약 전반 근거 (2026-10-02): 법령 조각 + 보고 있는 공고의 모집공고문 조각. 사이트(GitHub Pages)에서 받아 6시간 기억
const DOCS = new Map();
async function docJson(env, fetchImpl, path) {
  const hit = DOCS.get(path); if (hit && Date.now() - hit[0] < 6 * 3600e3) return hit[1];
  let j = null;
  try { const res = await fetchImpl(`${env.DOCS_BASE || 'https://cheongyakpass.kr'}/${path}`, { cf: { cacheTtl: 21600 } }); if (res.ok) j = await res.json(); } catch (e) {}
  DOCS.set(path, [Date.now(), j]); return j;
}

// 이번 달 추정 사용액 (Haiku 4.5: 입력 $1 · 출력 $5 / 100만 토큰). KV 'mspend:YYYY-MM' 에 달러로 쌓는다
const MONTH = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 7);
export const monthCap = env => +(env.CHAT_MONTH_USD || 18);
export async function monthSpent(kv) { return kv ? +((await kv.get('mspend:' + MONTH())) || 0) : 0; }
async function addMonthSpent(kv, attempts) {
  const usd = attempts.reduce((n, a) => n + (a.usage ? (a.usage.input_tokens || 0) / 1e6 + (a.usage.output_tokens || 0) * 5 / 1e6 : 0), 0);
  if (kv && usd) await kv.put('mspend:' + MONTH(), String((await monthSpent(kv)) + usd), { expirationTtl: 40 * 86400 });
}
function badRequest(msg) { return { status: 400, body: { error: msg } }; }

// 테스트에서도 그대로 부르는 본체. deps 로 fetch·KV·근거 색인을 바꿔 끼울 수 있다.
export async function handleChat(env, input, deps = {}) {
  const t0 = Date.now();
  const fetchImpl = deps.fetch || fetch;
  const kv = deps.kv || env.CHAT_KV;
  const { question, engine, anon_id, conversation_id, history, ip } = input || {};
  if (typeof question !== 'string' || !question.trim() || question.length > 500) return badRequest('질문은 1~500자');
  if (engine != null && (!VERDICTS.includes(engine.verdict) || !engine.listing || !Array.isArray(engine.items))) return badRequest('engine 결과 형식 오류');   // engine 없이(청약 전반 질문)도 받는다
  const listingId = String((engine && engine.listing.id) || input.listing_id || '');
  if (typeof anon_id !== 'string' || anon_id.length < 8) return badRequest('anon_id 필요');
  const isOp = !!(env.CHAT_PREVIEW_CODE && input.preview === env.CHAT_PREVIEW_CODE);
  const mode = kv ? await kv.get('mode') : null;   // 'maint' | 'open' | null — 운영자가 '!점검'·'!오픈'으로 바꾼다
  // 운영자 명령 (미리보기 코드가 맞을 때만): !점검 = 점검 모드(모두에게 멈춤), !오픈 = 다시 켜기(공개 열기). 질문 횟수에 세지 않는다
  const cmd = question.trim();
  // !무료 = 운영자 시험 모드(운영자 질문만 AI 를 부르지 않고 고정 문구로 답, 하루 횟수 제한 없음), !AI = 운영자도 실제 AI·횟수 제한으로 돌아감
  const lc = cmd.toLowerCase();
  if (isOp && (cmd === '!무료' || lc === '!ai' || cmd === '!유료')) {
    if (cmd === '!무료') await kv.put('opfree', '1'); else await kv.delete('opfree');
    return { status: 200, body: { kind: 'admin', mode: mode || 'preview', message: cmd === '!무료'
      ? '운영자 무료 시험 모드예요. 내 질문은 AI 를 부르지 않고(토큰 0) 기본 답으로, 횟수 제한 없이 받아요. 다른 이용자에게는 영향 없어요. 실제 AI 로 돌아가려면 !AI'
      : '운영자도 실제 AI 답으로 돌아왔어요(토큰 사용, 하루 2건 제한). 무료 시험은 !무료' } };
  }
  const opFree = isOp && kv ? (await kv.get('opfree')) === '1' : false;
  if (isOp && (cmd === '!점검' || cmd === '!오픈' || cmd === '!상태')) {
    if (cmd === '!점검') await kv.put('mode', 'maint');
    if (cmd === '!오픈') await kv.put('mode', 'open');
    const now = cmd === '!점검' ? 'maint' : cmd === '!오픈' ? 'open' : mode;
    const spent = await monthSpent(kv);
    return { status: 200, body: { kind: 'admin', mode: now || 'preview', message: (now === 'maint' ? '점검 모드로 바꿨어요. 모든 이용자에게 \'점검 중\'으로 보여요. 다시 켜려면 !오픈' : now === 'open' ? '청약봇을 켰어요. 공개 기간이면 모든 이용자가 쓸 수 있어요. 멈추려면 !점검' : '지금은 미리보기(운영자만)예요.')
      + ` · 이번 달 추정 사용액 $${spent.toFixed(2)} / 서버 한도 $${monthCap(env)}` + (opFree ? ' · 운영자 무료 시험 모드(AI 안 부름, 제한 없음)' : ' · 운영자 실제 AI 모드') } };
  }
  if (mode === 'maint') return { status: 503, body: { maint: true, message: '지금은 청약봇 점검 중이에요. 잠시 뒤 다시 이용해 주세요.' } };
  // 공개 전(CHAT_OPEN 이 '1' 도 아니고 !오픈 도 안 함)에는 미리보기 코드를 아는 운영자만
  if (env.CHAT_OPEN !== '1' && mode !== 'open' && !isOp) return { status: 403, body: { closed: true, message: '아직 준비 중인 기능이에요.' } };

  const lim = opFree ? { ok: true, followUp: false, followN: 0, remaining: null } : await checkLimit(kv, { anonId: anon_id, ip: ip || '', conversationId: conversation_id, salt: env.CHAT_STATS_TOKEN || '' });
  if (!lim.ok) { await bump(kv, { ['limited_' + lim.reason]: true }); return { status: 429, body: { limited: lim.reason, message: LIMIT_TEXT[lim.reason] } }; }

  const q = redact(question);
  const hist = (Array.isArray(history) ? history : []).slice(-4).map(h => ({ role: h.role, text: redact(h.text).text }));
  const intent = classify(q.text);
  const log = { intent, verdict: engine ? engine.verdict : null, listing: !!listingId, pii: q.found, prompt: PROMPT_VERSION, model: MODEL };

  if (intent === 'out_of_scope') {
    await markConversation(kv, conversation_id, false);
    await bump(kv, { q: true, follow_up: lim.followUp, intent, pii: q.found.length > 0 });
    return { status: 200, body: { kind: 'out_of_scope', message: OUT_OF_SCOPE_TEXT, pii: q.found, remaining: lim.remaining, log } };
  }

  let evidence;
  if (deps.evidence) evidence = selectEvidence(deps.evidence, engine, q.text).evidence;   // 예전 근거(공고문 발췌 태그) — 골든셋 시험용
  else {
    const nid = listingId.split('-')[0];
    const [law, notice] = await Promise.all([deps.law !== undefined ? deps.law : docJson(env, fetchImpl, 'chat-law.json'),
      deps.notice !== undefined ? deps.notice : /^\d{6,12}$/.test(nid) ? docJson(env, fetchImpl, `chat-notice/${nid}.json`) : null]);
    evidence = selectGeneral({ law, notice, question: q.text, engineItems: engine ? engine.items : [] });
  }
  const ctx = { engine, evidence, question: q.text };

  let answer = null, attempts = [];
  const apiKey = env.ANTHROPIC_API_KEY;
  const overBudget = (await monthSpent(kv)) >= monthCap(env);   // 이번 달 추정 사용액이 서버 한도에 닿으면 AI 없이 고정 문구로만 (콘솔 월 한도 앞의 안전장치)
  if ((apiKey || deps.llm) && !overBudget && !opFree) {
    let user = buildUserMessage({ question: q.text, intent, engine: engine || null, evidence, history: hist, listing: input.listing || null });
    for (let i = 0; i < 2 && !answer; i++) {
      try {
        const r = deps.llm ? await deps.llm({ system: SYSTEM, user, attempt: i }) : await callClaude({ apiKey, system: SYSTEM, user, fetchImpl });
        const v = validate(r.text, ctx);
        attempts.push({ ok: v.ok, flags: v.flags, usage: r.usage || null });
        if (v.ok) answer = v.answer;
        else user += `\n\nPREVIOUS_ANSWER_REJECTED: ${v.flags.join(' / ')}\n위 문제를 고쳐 JSON 으로 다시 써라.`;
      } catch (e) {
        attempts.push({ ok: false, flags: ['호출 실패: ' + e.message] });
        break;
      }
    }
  }
  const usedFallback = !answer;
  if (!answer) answer = deps.evidence ? fallbackAnswer({ engine, evidence, intent }) : fallbackGeneral({ engine, evidence, intent });
  await markConversation(kv, conversation_id, !!answer.ask, lim.followUp ? lim.followN + 1 : 0);

  const used = new Set([...(answer.why || []), ...(answer.official || [])].flatMap(x => x.refs || []));
  const sources = evidence.filter(e => used.has(e.id)).map(e => ({ id: e.id, kind: e.kind, title: e.title, url: e.kind === 'engine' ? (engine && engine.listing.link) : e.url, quote: e.text.slice(0, 200) }));
  await addMonthSpent(kv, attempts);
  await bump(kv, { over_budget: overBudget, q: true, follow_up: lim.followUp, intent, verdict: engine ? engine.verdict : 'general', pii: q.found.length > 0, ai_calls: attempts.filter(a => a.usage || a.ok || a.flags.length).length,
    rejected: attempts.filter(a => !a.ok).length, fallback: usedFallback,
    in_tokens: attempts.reduce((n, a) => n + ((a.usage && a.usage.input_tokens) || 0), 0), out_tokens: attempts.reduce((n, a) => n + ((a.usage && a.usage.output_tokens) || 0), 0) });
  Object.assign(log, { attempts: attempts.map(a => ({ ok: a.ok, flags: a.flags.length })), fallback: usedFallback, ms: Date.now() - t0 });
  return {
    status: 200,
    body: {
      kind: 'answer', verdict: engine ? engine.verdict : null, answer, sources,
      notice: '참고용이에요. 신청 전 모집공고문과 청약홈에서 꼭 확인하세요.',
      pii: q.found, follow_up: lim.followUp, remaining: lim.remaining, fallback: usedFallback, log,
    },
  };
}

// 답변 평가: 좋아요·아쉬워요와 이유만 하루 합계로 (질문·답변 원문은 받지 않는다)
export async function handleFeedback(env, input, deps = {}) {
  const kv = deps.kv || env.CHAT_KV;
  const { vote, reason, recheck } = input || {};
  if (!['up', 'down'].includes(vote)) return badRequest('vote 는 up 또는 down');
  if (reason != null && !(reason in FEEDBACK_REASONS)) return badRequest('reason 값 오류');
  await bump(kv, { ['fb_' + vote]: true, fb_reason: reason || null, recheck: ['same', 'changed'].includes(recheck) ? recheck : null });
  return { status: 200, body: { ok: true } };
}

function cors(env, origin) {
  const allowed = String(env.ALLOWED_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean);
  return allowed.includes(origin) ? { 'access-control-allow-origin': origin, 'access-control-allow-methods': 'POST, OPTIONS', 'access-control-allow-headers': 'content-type', vary: 'origin' } : null;
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    // 운영자 수집 작업(collect.yml)이 하루 합계를 가져간다 — 비밀 토큰이 있어야 함
    if (request.method === 'GET' && path === '/stats') {
      const ok = env.CHAT_STATS_TOKEN && request.headers.get('authorization') === 'Bearer ' + env.CHAT_STATS_TOKEN;
      if (!ok) return new Response('unauthorized', { status: 401 });
      return new Response(JSON.stringify(await readStats(env.CHAT_KV, 7)), { headers: { 'content-type': 'application/json; charset=utf-8' } });
    }
    if (request.method === 'GET' && path === '/health') { const mode = env.CHAT_KV ? await env.CHAT_KV.get('mode') : null;
      return new Response(JSON.stringify({ ok: true, open: env.CHAT_OPEN === '1' || mode === 'open', maint: mode === 'maint', model: MODEL, prompt: PROMPT_VERSION, key: !!env.ANTHROPIC_API_KEY }), { headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*', 'cache-control': 'max-age=60' } }); }
    const origin = request.headers.get('origin') || '';
    const h = cors(env, origin);
    if (!h) return new Response('forbidden', { status: 403 });
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: h });
    if (request.method !== 'POST' || !['/chat', '/feedback'].includes(path)) return new Response('not found', { status: 404, headers: h });
    const len = +(request.headers.get('content-length') || 0);
    if (len > 40000) return new Response('too large', { status: 413, headers: h });
    let input;
    try { input = await request.json(); } catch (e) { return new Response('bad json', { status: 400, headers: h }); }
    input.ip = request.headers.get('cf-connecting-ip') || '';
    const r = path === '/feedback' ? await handleFeedback(env, input) : await handleChat(env, input);
    if (r.body && r.body.log) { console.log(JSON.stringify(r.body.log)); delete r.body.log; }   // 개인정보 없는 집계만 로그로
    return new Response(JSON.stringify(r.body), { status: r.status, headers: { ...h, 'content-type': 'application/json; charset=utf-8' } });
  },
};
