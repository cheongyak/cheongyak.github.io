// docs/rules-evidence.txt(2.4MB)를 공고번호별 작은 파일 docs/chat-evidence/<번호>.json 으로 나눈다.
// 청약봇 서버(Cloudflare Worker 무료 한도: 호출당 CPU 10ms)는 큰 파일을 풀 수 없어, 물어본 공고의 조각만 받아 쓴다.
// 사용: node chat/tools/split_evidence.mjs [저장소 경로]  (probe.yml 이 근거 자료를 모은 뒤 실행)
import fs from 'node:fs';
import { parseEvidence } from '../worker/src/evidence.js';
const REPO = process.argv[2] || new URL('../..', import.meta.url).pathname;
const idx = parseEvidence(fs.readFileSync(REPO + '/docs/rules-evidence.txt', 'utf8'));
const dir = REPO + '/docs/chat-evidence';
fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
let n = 0, bytes = 0;
for (const [nid, v] of idx) { const s = JSON.stringify(v); fs.writeFileSync(`${dir}/${nid}.json`, s); n++; bytes += s.length; }
console.log(`[청약봇 근거] 공고 ${n}건 · 평균 ${n ? Math.round(bytes / n / 1024) : 0}KB`);
