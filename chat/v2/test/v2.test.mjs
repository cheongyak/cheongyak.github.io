// 청약봇 V2 시험: node --test chat/v2/test/
// 1) 조건 해석 시험지(golden/questions.json) 2) 검색 결과를 oracle.mjs(따로 옮긴 계산)로 검산 3) 판정이 화면 엔진과 같음 4) 답 모양·지어내기 검사
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { extract, applyDelta } from '../extract.mjs';
import { search, mergeRegions } from '../search.mjs';
import { loadData } from '../node-data.mjs';
import { ask } from '../node.mjs';
import { checkAnswer, parseExtraction, factsForLLM } from '../llm.mjs';
import { oracleRequired, liveStatus } from './oracle.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const G = JSON.parse(readFileSync(join(HERE, '../golden/questions.json'), 'utf8'));
const TODAY = '2026-10-02';
const FIX = JSON.parse(readFileSync(join(HERE, 'fixture-listings.json'), 'utf8'));   // 고정 데이터 (매일 수집이 바뀌어도 시험은 같게)
const D = loadData({ today: TODAY, listings: FIX, past: false });
const DO = { listings: FIX, past: false };
const PROFILE = JSON.parse(readFileSync(join(HERE, 'profile-newlywed.json'), 'utf8'));

const has = (C, e) => C.conds.some(c => c.key === e.key && (!e.weight || c.weight === e.weight) && (e.value === undefined || JSON.stringify(c.value) === JSON.stringify(e.value))
  && (!e.label || (Array.isArray(c.value) && c.value.some(v => v.label === e.label))) && (!e.place || c.value.place === e.place) && (!e.who || c.value.who === e.who)
  && (e.bed === undefined || c.value.bed === e.bed) && (e.bath === undefined || c.value.bath === e.bath) && (e.explore_ok === undefined || !!c.explore_ok === e.explore_ok));

for (const g of G.items) test('조건 해석 ' + g.id + ' — ' + g.q.slice(0, 30), () => {
  const C = extract(g.q), e = g.expect;
  if (e.intent) assert.equal(C.intent, e.intent);
  for (const x of e.conds || []) assert.ok(has(C, x), '없는 조건 ' + JSON.stringify(x) + '\n해석: ' + JSON.stringify(C.conds.map(c => [c.key, c.weight, c.text])));
  for (const x of e.not || []) assert.ok(!has(C, x), '있으면 안 되는 조건 ' + JSON.stringify(x));
  for (const [k, v] of Object.entries(e.assume || {})) assert.equal(C.assume[k], v, 'assume.' + k);
  if (e.targets) assert.equal(C.targets.length, e.targets);
  if (e.unsupported_has) assert.ok(C.unsupported.some(u => u.includes(e.unsupported_has)), '형식 밖 조건 표시 없음: ' + e.unsupported_has);
  if (e.scope_past) assert.equal(C.scope.past, true);
  for (const p of e.perspectives || []) assert.ok(C.perspectives.includes(p));
});

for (const g of G.deltas) test('후속 질문 ' + g.id, () => {
  const C = applyDelta(extract(g.first), g.then);
  for (const x of g.expect || []) assert.ok(has(C, x), '없는 조건 ' + JSON.stringify(x) + ' ' + JSON.stringify(C.conds.map(c => [c.key, c.text])));
  for (const x of g.expect_not || []) assert.ok(!has(C, x), '남은 조건 ' + JSON.stringify(x));
});

test('검색 검산: 후보는 필수 조건을 모두 통과(oracle), 빠진 주택형은 oracle 로도 하나 이상 불통과', () => {
  let n = 0;
  for (const g of G.items) {
    const C = mergeRegions(extract(g.q)); if (C.intent !== 'search') continue;
    const r = search(D, C, { profile: null });
    const req = C.conds.filter(c => c.weight === 'required');
    const shown = new Set([...r.ok, ...r.unsure].map(x => x.f.id));
    for (const x of FIX.filter(x => !x.sample)) {
      const st = liveStatus(x, TODAY);
      if (!C.conds.some(c => c.key === 'status') && !['접수 중', '접수 예정'].includes(st)) continue;
      const res = req.map(c => oracleRequired(x, c, TODAY)).filter(s => s !== 'skip');
      const ok = !res.includes('fail'), skipAll = req.some(c => oracleRequired(x, c, TODAY) === 'skip');
      if (shown.has(x.id)) assert.ok(ok, g.id + ' 후보 ' + x.id + ' 가 필수 조건을 어김 ' + JSON.stringify(req.map(c => [c.key, oracleRequired(x, c, TODAY)])));
      else if (!skipAll && ok) assert.fail(g.id + ' ' + x.id + ' 는 조건에 맞는데 빠짐');
      n++;
    }
  }
  assert.ok(n > 100);
});

test('판정은 화면 엔진 그대로: 후보의 elig 가 eligBucket 과 같고, 저장된 조건이 없으면 판정하지 않음', () => {
  const C = extract('수도권 10억 이하 청약');
  const r1 = search(D, C, { profile: null });
  assert.ok([...r1.ok, ...r1.unsure].every(x => x.elig === undefined));
  const r2 = search(D, C, { profile: PROFILE }), p = D.profileOf(PROFILE);
  for (const x of [...r2.ok, ...r2.unsure, ...r2.refused]) assert.equal(x.elig, D.E.eligBucket(x.row.L, p));
  assert.ok(r2.refused.every(x => x.elig === 'no') && r2.ok.every(x => x.elig !== 'no'));
});

test('결과 없을 때: 없다고 분명히, 이유·완화안·알림', async () => {
  const a = await ask({ question: '송파 청약 있어?', today: TODAY, dataOpts: DO });
  assert.match(a.text, /청약은 없어요/);
  assert.match(a.text, /왜 없는지/);
  assert.match(a.text, /새 공고 알림/);
});

test('비교: 찾은 단지는 지표 카드, 못 찾은 단지는 이유를 말함', async () => {
  const a = await ask({ question: '은빛 1,2단지 vs 도봉 한신 vs 방학 청구 비교해주고 급지 및 호재 비교해줘', today: TODAY, dataOpts: DO });
  assert.equal(a.mode, 'compare');
  assert.match(a.text, /찾지 못했어요/);
  assert.match(a.text, /급지·호재.*데이터가 없어/);
  const b = await ask({ question: '광명 시티프라디움 에듀하임 vs 강변역 센트럴 아이파크 어디가 나아?', today: TODAY, dataOpts: DO });
  assert.match(b.text, /광명 시티프라디움 에듀하임 \(/); assert.match(b.text, /강변역 센트럴 아이파크 \(/);
});

test('방·출퇴근: 데이터 없는 값은 확인 불가로, 시간을 지어내지 않음', async () => {
  const a = await ask({ question: G.items[0].q, today: TODAY, dataOpts: DO });
  assert.match(a.text, /방·욕실/);
  assert.match(a.text, /출퇴근 시간 — 경로 조회를 아직 연결하지 않아/);
  assert.doesNotMatch(a.text, /\d+분 (걸|소요)/);
});

test('기본 답은 스스로 검사기를 통과한다 (숫자·판정이 사실 묶음과 같음)', async () => {
  for (const q of ['신혼부부인데 현금 3억 있어요. 수도권에서 10억 이하로 신청 가능한 공고 추천해줘', '경기도 30평대 9억 이하 무순위 있어?', '시세차익 큰 로또 청약 추천']) {
    const a = await ask({ question: q, profile: PROFILE, today: TODAY, dataOpts: DO });
    const chk = checkAnswer(a.text, a.facts);
    assert.ok(chk.ok, q + ' → ' + chk.flags.join(' / '));
  }
});

test('검사기: 지어낸 숫자·판정 뒤집기·급지 단정을 막음', async () => {
  const a = await ask({ question: '신혼부부인데 현금 3억 있어요. 수도권에서 10억 이하로 신청 가능한 공고 추천해줘', profile: PROFILE, today: TODAY, dataOpts: DO });
  assert.ok(!checkAnswer(a.text + '\n분양가 3.33억짜리도 있어요', a.facts).ok);
  const top = a.facts.candidates[0];
  assert.ok(!checkAnswer(a.text.replace(top.name + ' (', top.name + ' (일반공급 신청 불가 '), a.facts).ok || top.elig === 'no');
  assert.ok(!checkAnswer(a.text + '\n이 동네는 4급지라 호재로 오를 거예요', a.facts).ok);
});

test('AI 조건 해석 검사: 질문에 없는 조건·모르는 key·필수 조건 지우기를 거절', () => {
  const C = extract('분당 제외 20억 이하');
  assert.equal(parseExtraction('{"conds":[{"key":"price_max","value":20,"weight":"required","text":"20억 이하"}]}', C).ok, false);   // 분당 제외를 지움
  assert.equal(parseExtraction('{"conds":[{"key":"region_out","value":[],"weight":"required","text":"분당 제외"},{"key":"price_max","value":20,"weight":"required","text":"20억 이하"},{"key":"view","value":1,"weight":"required","text":"한강뷰"}]}', C).ok, false);
  assert.equal(parseExtraction('{"conds":[{"key":"region_out","value":[],"weight":"required","text":"분당 제외"},{"key":"price_max","value":20,"weight":"required","text":"20억 이하"},{"key":"rooms","value":{"bed":4},"weight":"required","text":"방4개"}]}', C).ok, false);
  assert.equal(parseExtraction('{"conds":[{"key":"region_out","value":[],"weight":"required","text":"분당 제외"},{"key":"price_max","value":20,"weight":"required","text":"20억 이하"}]}', C).ok, true);
  assert.equal(parseExtraction('이건 JSON 아님', C).ok, false);
});

test('AI 가 있으면 두 번만 부르고, 거절되면 기본 답으로', async () => {
  const calls = [];
  const llm = async ({ purpose }) => { calls.push(purpose); return purpose === 'extract' ? 'not json' : '짧음'; };
  const a = await ask({ question: '경기도 30평대 9억 이하 무순위 있어?', today: TODAY, dataOpts: DO, llm });
  assert.deepEqual(calls, ['extract', 'explain']);
  assert.equal(a.how, 'template');
  assert.ok(a.steps.some(s => /거절/.test(s)));
});
