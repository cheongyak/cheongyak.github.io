// 답 품질 측정·진화 실행기.
//   node chat/v2/quality/run.mjs            → 시험지(golden) + 생성 질문 × (내 조건 없음, 신혼부부 조건) 을 답하고 채점 → evidence/chat-v2/quality.json·quality-report.md
//   node chat/v2/quality/run.mjs --ratchet  → 이번 점수가 기준선보다 높으면 기준선을 올린다 (내려가지는 않음 — 래칫)
// 진화 순환: ① 채점 → ② 약점 순위(어느 검사가 몇 번, 점수 손실이 큰 순) + 못 읽은 낱말 후보(해석에 안 잡힌 말) → ③ 사람이(또는 Claude 가) 고침 → ④ 다시 채점, 기준선보다 낮으면 실패(CI) → ⑤ 래칫으로 기준 올림.
// 실제 사용자 평가(👍👎 이유 7가지, 청약봇 서버 /stats 합계)는 같은 약점 이름으로 모아 ②에 더한다(feedback.json, 공개 뒤).
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ask, data } from '../node.mjs';
import { runINV, runDIR } from './checklist.mjs';
import { score, DIMS } from './rubric.mjs';
import { generate } from './generate.mjs';

const HERE = dirname(fileURLToPath(import.meta.url)), ROOT = join(HERE, '../../..');
const args = process.argv.slice(2);
const TODAY = '2026-10-02';
const FIX = JSON.parse(readFileSync(join(HERE, '../test/fixture-listings.json'), 'utf8'));   // 고정 데이터 — 회차끼리 같은 조건으로 비교
const PROFILE = JSON.parse(readFileSync(join(HERE, '../test/profile-newlywed.json'), 'utf8'));
const G = JSON.parse(readFileSync(join(HERE, '../golden/questions.json'), 'utf8'));
const BASE_F = join(HERE, 'baseline.json');

const qs = [...G.items.map(x => ({ ...x, src: 'golden' })), ...generate(Number(process.env.GEN_N || 120)).map(x => ({ ...x, src: 'gen' }))];
const rows = [];
for (const x of qs) for (const [pn, prof] of [['조건 없음', null], ['신혼부부', PROFILE]]) {
  const a = await ask({ question: x.q, profile: prof, today: TODAY, dataOpts: { listings: FIX, past: false }, commute: null, geocode: null });
  if (a.mode === 'explain') continue;   // 제도 설명은 아직 기존 청약봇 경로
  a.profileGiven = !!prof;
  const s = score({ q: x.q, a, expect: x.expect && x.expect.conds ? x.expect : null });
  rows.push({ id: x.id, src: x.src, profile: pn, mode: a.mode, ...s, residue: residue(x.q, a.state) });
}

// 못 읽은 낱말: 질문에서 해석 근거(text)·흔한 말로 설명되지 않은 낱말 → 사전(lexicon) 보강 후보
function residue(q, C) {
  const used = (C.conds || []).map(c => String(c.text || '')).join(' ') + ' ' + JSON.stringify(C.assume || {}) + ' ' + (C.targets || []).join(' ');
  const STOP = /^(청약|추천해줘|추천|알려줘|있어|있어\?|찾아줘|공고|곳|넣을|만한|위주로|좋겠어|이면|으로|로|에서|하고|이고|인데|있는데|이에요|예요|저는|우리|키우는|키우고|있고|가족이에요|꼭|빼고|말고|이하|이하로|안쪽|까지|이상|중에|아파트|좀|요|는|은|이|가|를|을|도|만|나|이나|해줘|해주세요|싶어|싶은데|괜찮아|돼|되는|수|있는|된|건|거|게|것|뭐|어디|지금|이번|직장|남편|아내|와이프)$/;
  return [...new Set(q.replace(/[(),.?!]/g, ' ').split(/\s+/).filter(w => w.length >= 2 && !STOP.test(w) && !used.includes(w.replace(/(은|는|이|가|을|를|도|에|으로|로|이에요|예요|이고)$/, ''))))].slice(0, 6);
}

// CheckList 행동 테스트
const INV = runINV(qs), DIR = runDIR(data({ today: TODAY, listings: FIX, past: false }), qs.filter(x => x.src === 'gen'));
const invRate = INV.length ? Math.round(INV.filter(r => r.ok).length / INV.length * 1000) / 10 : null, dirRate = DIR.length ? Math.round(DIR.filter(r => r.ok).length / DIR.length * 1000) / 10 : null;
const invFail = {}; INV.filter(r => !r.ok).forEach(r => { const k = r.from + ' → ' + r.to; (invFail[k] = invFail[k] || { n: 0, ex: r }).n++; });
const avg = xs => xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length * 10) / 10 : null;
const dimAvg = {}; for (const d of Object.keys(DIMS)) dimAvg[d] = Math.round(avg(rows.map(r => r.dims[d] * 100)) * 10) / 10;
const hard = rows.filter(r => r.hardFail.length);
// 약점 순위: 검사별 (실패 횟수 × 평균 손실 × 차원 무게)
const W = {}; for (const r of rows) for (const i of r.issues) { const k = i.dim + '·' + i.id; (W[k] = W[k] || { dim: i.dim, id: i.id, n: 0, loss: 0, ex: [] }); W[k].n++; W[k].loss += (1 - i.s) * DIMS[i.dim]; if (W[k].ex.length < 3) W[k].ex.push({ q: r.q.slice(0, 70), profile: r.profile, why: i.why.slice(0, 140) }); }
// 실제 사용자 평가(공개 뒤): 청약봇 서버 하루 합계의 '👎 이유' 7가지를 같은 약점 이름으로 더한다 — evidence/chat-v2/feedback.json {reason: 횟수}
const FB_MAP = { wrong_info: ['정확', 'facts'], differs: ['정확', 'facts'], not_answered: ['이해', 'recall'], hard: ['읽기', 'tone'], too_long: ['읽기', 'length'], no_source: ['완결', 'card-source'], other: ['실용', 'narrow-q'] };
const FB_F = join(ROOT, 'evidence/chat-v2/feedback.json');
if (existsSync(FB_F)) for (const [reason, n] of Object.entries(JSON.parse(readFileSync(FB_F, 'utf8')).reasons || {})) { const [dim, id] = FB_MAP[reason] || ['실용', 'other']; const k = dim + '·' + id;
  (W[k] = W[k] || { dim, id, n: 0, loss: 0, ex: [] }); W[k].n += n; W[k].loss += n * 0.05 * DIMS[dim]; W[k].ex.unshift({ q: '(실제 사용자 👎 ' + n + '회)', profile: '-', why: reason }); }
const backlog = Object.values(W).sort((a, b) => b.loss - a.loss).map(x => ({ ...x, loss: Math.round(x.loss * 1000) / 1000 }));
const resid = {}; rows.filter(r => r.profile === '조건 없음').forEach(r => r.residue.forEach(w => { resid[w] = (resid[w] || 0) + 1; }));
const SL = rows.filter(r => r.profile === '조건 없음' && r.slots), TP = SL.reduce((a, r) => a + r.slots.tp, 0), FP = SL.reduce((a, r) => a + r.slots.fp, 0), FN = SL.reduce((a, r) => a + r.slots.fn, 0), J = SL.filter(r => r.slots.jga != null);
const slotF1 = TP ? Math.round(2 * TP / (2 * TP + FP + FN) * 1000) / 10 : null, jga = J.length ? Math.round(J.filter(r => r.slots.jga === 1).length / J.length * 1000) / 10 : null;
const summary = { slot_f1: slotF1, jga, jga_n: J.length, inv: invRate, inv_n: INV.length, dir: dirRate, dir_n: DIR.length, at: new Date().toISOString(), answers: rows.length, questions: qs.length, score: avg(rows.map(r => r.total)), golden: avg(rows.filter(r => r.src === 'golden').map(r => r.total)), generated: avg(rows.filter(r => r.src === 'gen').map(r => r.total)),
  dims: dimAvg, hard_fails: hard.length };
const out = { summary, inv_fail: Object.entries(invFail).sort((a, b) => b[1].n - a[1].n).slice(0, 30).map(([k, v]) => ({ para: k, n: v.n, q: v.ex.q, want: v.ex.base, got: v.ex.got })), dir_fail: DIR.filter(r => !r.ok).slice(0, 20), backlog: backlog.slice(0, 25), residue: Object.entries(resid).sort((a, b) => b[1] - a[1]).slice(0, 30), worst: rows.slice().sort((a, b) => a.total - b.total).slice(0, 12).map(r => ({ q: r.q, profile: r.profile, total: r.total, hard: r.hardFail, top: r.issues.slice(0, 4) })), hard: hard.slice(0, 20).map(r => ({ q: r.q, profile: r.profile, hard: r.hardFail })) };
mkdirSync(join(ROOT, 'evidence/chat-v2'), { recursive: true });
writeFileSync(join(ROOT, 'evidence/chat-v2/quality.json'), JSON.stringify(out, null, 1) + '\n');

// 사람이 읽는 보고서
const base = existsSync(BASE_F) ? JSON.parse(readFileSync(BASE_F, 'utf8')) : null;
const md = [`# 청약봇 V2 답 품질 (${summary.at.slice(0, 16).replace('T', ' ')} UTC)`, '',
  `- **조건 해석: 슬롯 F1 ${slotF1} · Joint Goal Accuracy ${jga}%** (정답을 아는 생성 질문 ${J.length}개${base && base.jga != null ? ', 기준선 JGA ' + base.jga + '%' : ''})`,
  `- **CheckList: 말 바꿔도 같은 해석(INV) ${invRate}%** (${INV.length}쌍) · **조건을 더하면 후보가 줄기만(DIR) ${dirRate}%** (${DIR.length}쌍)`,
  `- 답 ${summary.answers}개 (질문 ${summary.questions} × 내 조건 2종) · **평균 ${summary.score}점**${base ? ` (기준선 ${base.score})` : ''} · 시험지 ${summary.golden} · 생성 질문 ${summary.generated} · 치명 실패 ${summary.hard_fails}개`,
  '', '| 차원 | 무게 | 점수 |' + (base ? ' 기준선 |' : ''), '|---|---|---|' + (base ? '---|' : ''), ...Object.entries(dimAvg).map(([d, v]) => `| ${d} | ${DIMS[d]} | ${v} |` + (base ? ` ${base.dims[d]} |` : '')),
  '', '## 약점 순위 (고치면 점수가 가장 많이 오르는 순)', ...backlog.slice(0, 12).map((b, i) => `${i + 1}. **${b.dim}·${b.id}** — ${b.n}회, 손실 ${b.loss}\n   - 예: ${b.ex[0] ? b.ex[0].why + ' ← "' + b.ex[0].q + '" (' + b.ex[0].profile + ')' : ''}`),
  '', '## 말 바꾸면 해석이 달라지는 표현 (INV 실패)', ...(Object.keys(invFail).length ? Object.entries(invFail).sort((a, b) => b[1].n - a[1].n).slice(0, 15).map(([k, v]) => `- ${k} (${v.n}회) — 예: "${v.ex.q.slice(0, 60)}"`) : ['- 없음']),
  '', '## 못 읽은 낱말 후보 (사전 보강 검토)', Object.entries(resid).sort((a, b) => b[1] - a[1]).slice(0, 20).map(([w, n]) => `${w}(${n})`).join(' · ') || '없음',
  '', '## 치명 실패', ...(hard.length ? hard.slice(0, 10).map(r => `- "${r.q}" (${r.profile}): ${r.hardFail.join(' / ')}`) : ['- 없음'])].join('\n');
writeFileSync(join(ROOT, 'evidence/chat-v2/quality-report.md'), md + '\n');
console.log(`[청약봇 품질] 조건 해석 슬롯 F1 ${slotF1} · JGA ${jga}% (${J.length}문항) · 말 바꿔도 같음(INV) ${invRate}% (${INV.length}) · 조건 더하면 줄기만(DIR) ${dirRate}% (${DIR.length}) · 답 ${summary.answers} · 평균 ${summary.score}${base ? ' (기준선 ' + base.score + ')' : ''} · 치명 ${summary.hard_fails} · ` + Object.entries(dimAvg).map(([d, v]) => d + ' ' + v).join(' · '));
backlog.slice(0, 8).forEach(b => console.log(`   ${b.dim}·${b.id} ${b.n}회 손실 ${b.loss} — ${b.ex[0] ? b.ex[0].why.slice(0, 90) : ''}`));

// 기준선: 래칫 (올라가기만)
let fail = summary.hard_fails > 0 ? '치명 실패 ' + summary.hard_fails + '개' : '';
if (base && !fail) { const drop = Object.entries(dimAvg).filter(([d, v]) => v < base.dims[d] - 0.5).map(([d, v]) => d + ' ' + base.dims[d] + '→' + v); if (base.jga != null && jga < base.jga - 1) drop.push('JGA ' + base.jga + '→' + jga);
  if (base.inv != null && invRate < base.inv - 1) drop.push('INV ' + base.inv + '→' + invRate);
  if (base.dir != null && dirRate < base.dir - 1) drop.push('DIR ' + base.dir + '→' + dirRate);
  if (summary.score < base.score - 0.3 || drop.length) fail = '기준선보다 낮음: 평균 ' + base.score + '→' + summary.score + (drop.length ? ' · ' + drop.join(', ') : ''); }
if (args.includes('--ratchet') && !fail) {
  const nb = { inv: Math.max(invRate || 0, base && base.inv || 0), dir: Math.max(dirRate || 0, base && base.dir || 0), jga: Math.max(jga || 0, base && base.jga || 0), slot_f1: Math.max(slotF1 || 0, base && base.slot_f1 || 0), score: Math.max(summary.score, base ? base.score : 0), dims: Object.fromEntries(Object.entries(dimAvg).map(([d, v]) => [d, Math.max(v, base ? base.dims[d] : 0)])), at: summary.at, answers: summary.answers };
  writeFileSync(BASE_F, JSON.stringify(nb, null, 1) + '\n'); console.log('   기준선 갱신:', nb.score);
}
if (fail) { console.log('   ✗ ' + fail); process.exit(1); }
