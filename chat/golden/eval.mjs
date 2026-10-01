// 골든셋 평가. 질문마다: 고정 공고 데이터로 엔진 결과를 만들고 → 챗봇 서버 본체(handleChat)를 그대로 돌리고 → 채점한다.
//   node golden/eval.mjs                       AI 없이(고정 문구 답) 기준선
//   node golden/eval.mjs --fixtures f.json      미리 써 둔 AI 답으로 (검사기 동작 확인)
//   ANTHROPIC_API_KEY=... node golden/eval.mjs  실제 Claude 로 (키가 생기면)
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { handleChat } from '../worker/src/index.js';
import { parseEvidence, selectEvidence } from '../worker/src/evidence.js';
import { validate } from '../worker/src/validate.js';
import { redact } from '../worker/src/redact.js';
const require = createRequire(import.meta.url);
const { loadEngine, buildEngine } = require('../tools/engine_payload.cjs');

const REPO = process.env.REPO || new URL('../..', import.meta.url).pathname.replace(/\/$/, '');
const args = process.argv.slice(2);
const fixtures = args.includes('--fixtures') ? JSON.parse(fs.readFileSync(args[args.indexOf('--fixtures') + 1], 'utf8')) : null;
const only = args.includes('--only') ? args[args.indexOf('--only') + 1] : null;

const golden = JSON.parse(fs.readFileSync(new URL('./golden_v0.json', import.meta.url), 'utf8')).filter(g => !only || g.id.startsWith(only));
const eng = loadEngine(REPO + '/docs', REPO + '/tests/judge/listings.json');
const evidence = parseEvidence(fs.readFileSync(REPO + '/docs/rules-evidence.txt', 'utf8'));

class MemKV { constructor() { this.m = new Map(); } async get(k) { return this.m.has(k) ? this.m.get(k) : null; } async put(k, v) { this.m.set(k, v); } async delete(k) { this.m.delete(k); } }
const S2V = { ok: '가능', fail: '불가', warn: '확인 필요' };
const BUCKET = { ok: '가능', unsure: '확인 필요', r2: '2순위만', no: '불가' };

// 엔진 결과가 판정 사례 기대값과 같은가 (판정 사례의 기대값은 공고문·법령 표로 따로 계산된 값)
function engineMatches(exp, e) {
  const item = k => e.items.find(i => i.k === k);
  const st = k => (item(k) || {}).s;
  switch (exp.fn) {
    case 'sp': { const r = e.special.find(x => x.type === exp.type); if (!r) return 'n/a';
      return r.v === S2V[exp.s] && (!exp.stage || r.stage === exp.stage); }
    case 'acct': return st('청약통장 가입기간') === exp['가입기간'] && (exp['예치금'] === undefined || st('예치금 (민영)') === exp['예치금']) ? true : (item('청약통장 가입기간') ? false : 'n/a');
    case 'pubgen': { const it = e.items.find(i => i.k.startsWith('소득')); return it ? it.s === exp['소득'] : 'n/a'; }
    case 'town': { for (const k of Object.keys(exp)) { if (['fn', 'type', 'item'].includes(k)) continue; const it = item(k + ' (신혼희망타운)'); if (!it) return 'n/a'; if (it.s !== exp[k]) return false; } return true; }
    case 'residence': { const it = item('거주지'); return it ? it.s === exp.s && it.v.includes(exp.v) : 'n/a'; }
    case 'score': return JSON.stringify(e.score.parts) === JSON.stringify(exp.parts);
    case 'bucket': return e.verdict === BUCKET[exp.b];
    case 'item': { const it = item(exp.item); return (it ? it.s : 'none') === exp.s ? true : (it ? false : 'n/a'); }
    case 'home': { const it = item('무주택 세대'); return it ? it.s === exp.s : 'n/a'; }
  }
  return 'n/a';
}

const rows = [];
for (const g of golden) {
  const engine = buildEngine(eng, g.listing, g.profile);
  const llm = fixtures && fixtures[g.id] ? async ({ attempt }) => ({ text: [].concat(fixtures[g.id])[Math.min(attempt, [].concat(fixtures[g.id]).length - 1)] }) : undefined;
  const env = { CHAT_OPEN: '1', ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY || '' };
  const r = await handleChat(env, { question: g.question, engine, anon_id: 'golden-' + g.id, conversation_id: 'c-' + g.id, ip: '1.1.1.1' }, { kv: new MemKV(), evidence, llm });
  const b = r.body, x = g.expect, checks = {};
  if (x.engine) checks.engine = engineMatches(x.engine, engine);
  if (x.kind) checks.kind = b.kind === x.kind;
  if (b.kind === 'answer') {
    const ctx = { engine, evidence: selectEvidence(evidence, engine, redact(g.question).text).evidence, question: redact(g.question).text };
    const v = validate(b.answer, ctx);
    checks.validator = v.ok || v.flags.join(' / ');
    checks.verdict_consistent = b.answer.verdict === engine.verdict;
    if (x.verdict) checks.verdict = engine.verdict === x.verdict || `엔진 ${engine.verdict}`;
    if (x.ask) checks.ask = !!b.answer.ask;
    if (x.item) { const it = engine.items.find(i => i.k === x.item.k); checks.item = it ? it.s === x.item.s : 'n/a'; }
    if (x.evidence_tags) { const tags = ctx.evidence.filter(e => e.kind === 'notice').map(e => e.tag); checks.evidence = x.evidence_tags.every(t => tags.includes(t)) || '근거에 ' + x.evidence_tags.join(',') + ' 없음'; }
  }
  if (x.intent) checks.intent = (b.log && b.log.intent) === x.intent || `분류 ${b.log && b.log.intent}`;
  if (x.pii) checks.pii = x.pii.every(p => (b.pii || []).includes(p)) || '가림 ' + (b.pii || []).join(',');
  if (x.not_in_answer) { const s = JSON.stringify(b); checks.not_in_answer = x.not_in_answer.every(w => !s.includes(w)) || '답에 금지 문자열'; }
  const fails = Object.entries(checks).filter(([, v]) => v !== true && v !== 'n/a');
  rows.push({ id: g.id, source: g.source, ok: fails.length === 0, fallback: b.fallback ?? null, checks, fails });
}

const by = k => rows.filter(r => r.checks[k] !== undefined && r.checks[k] !== 'n/a');
const pass = k => by(k).filter(r => r.checks[k] === true).length;
const line = (name, k) => by(k).length ? `  ${name}: ${pass(k)}/${by(k).length}` : null;
const mode = process.env.ANTHROPIC_API_KEY ? '실제 Claude' : fixtures ? '미리 쓴 AI 답' : 'AI 없음(고정 문구 답)';
console.log(`[골든셋 v0 · ${mode}] ${rows.filter(r => r.ok).length}/${rows.length} 통과`);
console.log([line('엔진 = 판정 사례 기대값', 'engine'), line('답 판정 = 엔진 판정', 'verdict_consistent'), line('검사기 통과', 'validator'), line('기대 판정', 'verdict'), line('되물음', 'ask'), line('항목 판정', 'item'), line('근거 태그', 'evidence'), line('질문 분류', 'intent'), line('범위 밖 처리', 'kind'), line('개인정보 가림', 'pii'), line('금지 문자열 없음', 'not_in_answer')].filter(Boolean).join('\n'));
const na = rows.filter(r => r.checks.engine === 'n/a').length;
if (na) console.log(`  (엔진 대조 불가 ${na}건: 고정 데이터에서 해당 항목이 화면 판정 목록에 안 나옴)`);
for (const r of rows.filter(r => !r.ok)) console.log(`  ✗ ${r.id}: ${r.fails.map(([k, v]) => k + '=' + (v === false ? '불일치' : v)).join(' · ')}`);
fs.writeFileSync(new URL('./eval_result.json', import.meta.url), JSON.stringify({ mode, at: new Date().toISOString(), rows }, null, 1));
process.exitCode = rows.every(r => r.ok) ? 0 : 1;
