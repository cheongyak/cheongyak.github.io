// AI 품질 회차 (비용이 들어 운영자가 정할 때만 — Actions chat-v2-quality-ai.yml, ANTHROPIC_API_KEY 는 Secrets).
// 질문 n개마다: 기본 답(코드) · AI 설명 답(llm.mjs explainPrompt, 검사기 통과한 것만) → AI 심사(절대 평가 + 자리 바꾼 짝 비교) → Bradley-Terry 순위.
// 결과: evidence/chat-v2/ai-quality.json · ai-quality-report.md. 키·질문자 정보는 쓰지 않는다(시험용 질문·시험용 조건만).
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ask } from '../node.mjs';
import { generate } from './generate.mjs';
import { absolutePrompt, parseAbsolute, pairwise, bradleyTerry, CRITERIA } from './judge.mjs';
import { PROMPT_VERSION } from '../llm.mjs';

const HERE = dirname(fileURLToPath(import.meta.url)), ROOT = join(HERE, '../../..');
const CFG = JSON.parse(readFileSync(join(HERE, 'ai-run.json'), 'utf8'));
const KEY = process.env.ANTHROPIC_API_KEY;
if (!CFG.round) { console.log('[AI 품질] round 0 — 운영자가 회차를 시작하기 전이라 건너뜀 (ai-run.json 의 round 를 올리면 돈다)'); process.exit(0); }
if (!KEY) { console.log('[AI 품질] ANTHROPIC_API_KEY 없음 — 건너뜀'); process.exit(0); }
const usage = { in: 0, out: 0, calls: 0 }, FALLBACK = { done: false, why: '' };
const call = model => async ({ system, user, purpose }) => {
  if (FALLBACK.done && model !== CFG.explain_model) model = CFG.explain_model;
  const r = await fetch('https://api.anthropic.com/v1/messages', { method: 'POST', headers: { 'content-type': 'application/json', 'x-api-key': KEY, 'anthropic-version': '2023-06-01' },
    body: JSON.stringify({ model, max_tokens: purpose === 'explain' ? 1800 : 500, temperature: 0, system, messages: [{ role: 'user', content: user }] }) });
  if (!r.ok) {
    if ((r.status === 404 || r.status === 400) && model !== CFG.explain_model && !FALLBACK.done) { FALLBACK.done = true; FALLBACK.why = model + ' ' + r.status; console.log('[AI 품질] 심사 모델을 못 써서 ' + CFG.explain_model + ' 로 바꿈: ' + FALLBACK.why); }
    if (FALLBACK.done && model !== CFG.explain_model) return call(CFG.explain_model)({ system, user, purpose });
    throw new Error('claude ' + r.status);
  }
  const j = await r.json(); usage.in += (j.usage || {}).input_tokens || 0; usage.out += (j.usage || {}).output_tokens || 0; usage.calls++;
  return (j.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
};
const explainLLM = call(CFG.explain_model), judgeLLM = call(CFG.judge_model);
const FIX = JSON.parse(readFileSync(join(HERE, '../test/fixture-listings.json'), 'utf8'));
const PROFILE = JSON.parse(readFileSync(join(HERE, '../test/profile-newlywed.json'), 'utf8'));
const G = JSON.parse(readFileSync(join(HERE, '../golden/questions.json'), 'utf8')).items.filter(x => !/explain/.test(x.id));
const pool = [...(CFG.samples || []).map(q => ({ q })), ...G, ...generate(60)].slice(0, CFG.n);

const rows = [], games = [];
for (const x of pool) {
  const D = { today: '2026-10-02', dataOpts: { listings: FIX, past: false }, profile: PROFILE, commute: null, geocode: null };
  const base = await ask({ question: x.q, ...D });
  const ai = await ask({ question: x.q, ...D, llm: async ({ system, user, purpose }) => purpose === 'explain' ? explainLLM({ system, user, purpose }) : 'skip' });   // 조건 해석은 규칙 그대로, 설명만 AI
  const A = { id: 'template', text: base.text }, B = { id: 'ai-' + PROMPT_VERSION, text: ai.text, how: ai.how, rejected: ai.steps.filter(s => /거절|실패/.test(s)) };
  const sa = parseAbsolute(await judgeLLM({ ...absolutePrompt(x.q, A.text), purpose: 'judge' })), sb = B.how === 'ai' ? parseAbsolute(await judgeLLM({ ...absolutePrompt(x.q, B.text), purpose: 'judge' })) : null;
  const g = B.how === 'ai' ? await pairwise(judgeLLM, x.q, A, B) : { a: A.id, b: B.id, winner: A.id, why: 'AI 답이 검사기에서 막혀 기본 답이 나감' };
  games.push(g);
  rows.push({ q: x.q, template: sa, ai: sb, ai_used: B.how === 'ai', ai_rejected: B.rejected, pair: g });
  console.log('·', x.q.slice(0, 40), '| 기본', sa ? sa.mean.toFixed(2) : '-', '| AI', sb ? sb.mean.toFixed(2) : '(막힘)', '| 승', g.winner);
}
const mean = k => { const xs = rows.map(r => r[k]).filter(Boolean); const o = {}; for (const c of Object.keys(CRITERIA)) o[c] = xs.length ? Math.round(xs.reduce((a, r) => a + r.scores[c], 0) / xs.length * 100) / 100 : null; o.평균 = xs.length ? Math.round(xs.reduce((a, r) => a + r.mean, 0) / xs.length * 100) / 100 : null; return o; };
const bt = bradleyTerry(games);
// 고칠 점 모으기: 심사위원이 '가장 먼저 고칠 점'으로 꼽은 말을 그대로 모은다 → 다음 회차 고칠 목록
const fixes = rows.flatMap(r => [r.template && r.template.fix, r.ai && r.ai.fix]).filter(Boolean);
const out = { at: new Date().toISOString(), cfg: CFG, prompt: PROMPT_VERSION, n: rows.length, template: mean('template'), ai: mean('ai'), ai_used: rows.filter(r => r.ai_used).length,
  judge_fallback: FALLBACK.why || null, bt, wins: Object.fromEntries(['template', 'ai-' + PROMPT_VERSION, 'tie'].map(k => [k, games.filter(g => g.winner === k).length])), usage, fixes, rows };
mkdirSync(join(ROOT, 'evidence/chat-v2'), { recursive: true });
writeFileSync(join(ROOT, 'evidence/chat-v2/ai-quality.json'), JSON.stringify(out, null, 1) + '\n');
writeFileSync(join(ROOT, 'evidence/chat-v2/ai-quality-report.md'), [`# 청약봇 AI 품질 회차 (${out.at.slice(0, 16)} UTC, 프롬프트 ${PROMPT_VERSION})`, '',
  `- 질문 ${out.n}개 · AI 설명이 검사기를 통과해 나간 답 ${out.ai_used}개 · 호출 ${usage.calls}회 · 토큰 입력 ${usage.in.toLocaleString()} / 출력 ${usage.out.toLocaleString()}`,
  `- 짝 비교 (자리 바꿔 두 번): 기본 답 승 ${out.wins.template} · AI 답 승 ${out.wins['ai-' + PROMPT_VERSION]} · 무 ${out.wins.tie}`,
  `- Bradley-Terry: ${Object.entries(bt).map(([k, v]) => k + ' Elo ' + v.elo).join(' · ')}`, '',
  '| 항목 | 기본 답 | AI 답 |', '|---|---|---|', ...[...Object.keys(CRITERIA), '평균'].map(c => `| ${c} | ${out.template[c]} | ${out.ai[c]} |`), '',
  '## 심사위원이 꼽은 고칠 점', ...fixes.slice(0, 20).map(f => '- ' + f)].join('\n') + '\n');
console.log(`[AI 품질] 기본 ${out.template.평균} · AI ${out.ai.평균} · 짝 비교 기본 ${out.wins.template} / AI ${out.wins['ai-' + PROMPT_VERSION]} / 무 ${out.wins.tie} · 호출 ${usage.calls} · 토큰 ${usage.in}/${usage.out}`);
