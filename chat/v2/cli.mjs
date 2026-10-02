// 사용: node chat/v2/cli.mjs "질문" [--profile 파일.json] [--today 2026-10-02] [--json]
// AI 없이 기본 답을 만든다 (AI 연결은 청약봇 서버에 붙일 때)
import { readFileSync } from 'node:fs';
import { ask } from './node.mjs';

const args = process.argv.slice(2), opt = k => { const i = args.indexOf(k); return i >= 0 ? args.splice(i, 2)[1] : null; };
const pf = opt('--profile'), today = opt('--today'), json = args.includes('--json');
const q = args.filter(a => a !== '--json').join(' ');
const profile = pf ? JSON.parse(readFileSync(pf, 'utf8')) : null;
const r = await ask({ question: q, profile, today });
if (json) console.log(JSON.stringify({ state: r.state, result: r.result, steps: r.steps, ms: r.ms }, null, 1));
else { console.log(r.text || r.legacy); console.log('\n— ' + r.steps.join(' · ') + ' · ' + r.ms + 'ms'); }
