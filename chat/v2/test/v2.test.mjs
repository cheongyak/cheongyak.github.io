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
  for (const [k, v] of Object.entries(e.plan || {})) assert.equal((C.plan || {})[k], v, 'plan.' + k);
  if (e.not_unsupported) assert.ok(!C.unsupported.some(u => u.includes(e.not_unsupported)), '없어야 할 형식 밖 표시: ' + e.not_unsupported);
  if (e.scope_expand !== undefined) assert.equal(!!C.scope.expand, e.scope_expand, '넓혀 보기(말고도)');
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
  assert.match(a.text, /비교해 드릴 수 없어요/); assert.match(a.text, /실거래가 공개시스템/);
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

test('출퇴근 조회: 네이버 실패하면 카카오, 둘 다 없으면 오류(시간을 지어내지 않음)', async () => {
  const { carTime } = await import('../commute.mjs');
  const A = { lat: 37.47, lng: 126.86 }, B = { lat: 37.39, lng: 127.11 };
  const naverOk = async () => ({ ok: true, status: 200, json: async () => ({ route: { trafast: [{ summary: { duration: 1860000, distance: 24500 } }] } }) });
  const fail = async () => ({ ok: false, status: 401, json: async () => ({ message: 'unauthorized' }) });
  const kakaoOk = async (u) => /kakaomobility/.test(u) ? { ok: true, status: 200, json: async () => ({ routes: [{ result_code: 0, summary: { duration: 1500, distance: 22000 } }] }) } : fail();
  const a = await carTime(A, B, { ncpId: 'x', ncpSecret: 'y', kakao: 'z' }, naverOk);
  assert.equal(a.min, 31); assert.equal(a.km, 24.5); assert.match(a.src, /네이버/);
  const b = await carTime(A, B, { ncpId: 'x', ncpSecret: 'y', kakao: 'z' }, kakaoOk);
  assert.equal(b.min, 25); assert.match(b.src, /카카오/);
  const c = await carTime(A, B, {}, naverOk);
  assert.ok(c.error && c.min === undefined);
});

test('출퇴근 시간이 오면 카드에 자동차 시간, 순서도 시간으로', async () => {
  const fake = async (a, b) => ({ min: Math.round(Math.hypot(a.lat - b.lat, a.lng - b.lng) * 100), km: 10, src: '네이버 Directions 5 (실시간 교통)', at: '2026-10-02T14:00:00.000Z' });
  const a = await ask({ question: '자녀 1명 키우고 남편 직장 구로, 아내 마포예요. 수도권 10억 이하 청약 추천해줘', today: TODAY, dataOpts: DO, profile: PROFILE, commute: fake });
  assert.match(a.text, /남편 구로구?까지 자동차 약 \d+분/);
  assert.ok(checkAnswer(a.text, a.facts).ok, checkAnswer(a.text, a.facts).flags.join('/'));
  const b = await ask({ question: '자녀 1명 키우고 남편 직장 구로, 아내 마포예요. 수도권 10억 이하 청약 추천해줘', today: TODAY, dataOpts: DO, profile: PROFILE, commute: null });
  assert.doesNotMatch(b.text, /자동차 약 \d+분/);
});

test('품질 채점기: 지어낸 숫자·과장은 0점, 정상 답은 높은 점수', async () => {
  const { score } = await import('../quality/rubric.mjs');
  const a = await ask({ question: '신혼부부인데 현금 3억 있어요. 수도권에서 10억 이하로 신청 가능한 공고 추천해줘', profile: PROFILE, today: TODAY, dataOpts: DO, commute: null, geocode: null });
  a.profileGiven = true;
  assert.ok(score({ q: 'x', a }).total >= 90);
  assert.equal(score({ q: 'x', a: { ...a, text: a.text + '\n분양가 3.33억짜리도 있어요' } }).total, 0);
  assert.equal(score({ q: 'x', a: { ...a, text: a.text + '\n이 곳은 무조건 당첨이에요' } }).total, 0);
});

test('AI 심사: 자리 바꿔 두 번 물어 엇갈리면 무승부, Bradley-Terry 는 이긴 쪽이 높음', async () => {
  const { pairwise, bradleyTerry } = await import('../quality/judge.mjs');
  const alwaysA = async () => '{"winner":"A","why":"자리 편향"}';
  const g1 = await pairwise(alwaysA, 'q', { id: 'x', text: '1' }, { id: 'y', text: '2' });
  assert.equal(g1.winner, 'tie');
  const prefersLong = async ({ user }) => { const a = user.split('[답 A]\n')[1].split('\n\n[답 B]')[0], b = user.split('[답 B]\n')[1]; return JSON.stringify({ winner: a.length > b.length ? 'A' : 'B', why: '' }); };
  const g2 = await pairwise(prefersLong, 'q', { id: 'x', text: '길고 자세한 답입니다 정말로' }, { id: 'y', text: '짧음' });
  assert.equal(g2.winner, 'x');
  const bt = bradleyTerry([{ a: 'x', b: 'y', winner: 'x' }, { a: 'x', b: 'y', winner: 'x' }, { a: 'x', b: 'y', winner: 'tie' }]);
  assert.ok(bt.x.elo > bt.y.elo);
});

test('CheckList: 말 바꾸기 표는 대부분 같은 해석, 조건을 더하면 후보가 늘지 않음', async () => {
  const { runINV, runDIR } = await import('../quality/checklist.mjs');
  const { generate } = await import('../quality/generate.mjs');
  const qs = generate(60);
  const inv = runINV(qs); assert.ok(inv.filter(r => r.ok).length / inv.length >= 0.97, 'INV ' + inv.filter(r => !r.ok).slice(0, 3).map(r => r.from + '→' + r.to).join(', '));
  const dir = runDIR(D, qs); assert.ok(dir.every(r => r.ok), dir.filter(r => !r.ok).slice(0, 2).map(r => r.why).join(' / '));
});


// 사용자 샘플 3 (2026-10-04): '마포구 말고도 같은 조건으로' → 그 지역 밖 후보 블록, '학군지 필요없어' → 학교 줄·학교 장점 없음, 이유를 이미 적은 확인 불가 항목에 말 덧붙이지 않음
test('샘플 3 — 넓혀 보기·학군 안 따짐·층 설명', async () => {
  const q = G.items.find(x => x.id === 'v2-sample3').q;
  const a = await ask({ question: q, today: TODAY, dataOpts: DO, profile: PROFILE });
  assert.ok(/밖 · 같은 조건\]/.test(a.text), '그 지역 밖 블록 없음');
  assert.ok(!/· 초등학교 /.test(a.text) && !/초등학교가 가까워요/.test(a.text), '학군 필요 없다는데 학교를 내세움');
  assert.ok(/동·호수를 추첨/.test(a.text), '저층 제외를 못 하는 이유 설명 없음');
  assert.ok(!/추첨으로 정해서 저층을 미리 뺄 수 없어요 — 청약패스에 이 데이터가/.test(a.text), '이유 뒤에 말 덧붙임');
  assert.ok(!/마포구 제외/.test(a.text), "'말고도'를 제외로 읽음");
  assert.ok(/4인 가족/.test(a.text.split('\n')[0]), '첫 줄에 상황 되짚기 없음');
});


// 사용자 샘플 4 (2026-10-04): 노선 조건 — 단지 좌표에서 그 노선 가장 가까운 역까지 직선거리. 역 좌표는 OpenStreetMap(chat/v2/data/lines.json), 시험은 고정 역으로
test('샘플 4 — 노선 역세권 판정·노선 현황·경기남부 정의', async () => {
  const { evalCond, nearestOn } = await import('../search.mjs');
  const st = [{ name: '가', lat: 37.5, lng: 127.0 }, { name: '나', lat: 37.6, lng: 127.1 }];
  assert.deepEqual(nearestOn(st, { lat: 37.5005, lng: 127.0 }), { name: '가', m: 56 });
  const D2 = { lines: { lines: { 신분당선: st } } }, c = { key: 'line', value: { line: '신분당선', m: 1000 } };
  assert.equal(evalCond(D2, {}, { geo: { lat: 37.503, lng: 127.0 } }, c, {})[0], 'pass');
  assert.equal(evalCond(D2, {}, { geo: { lat: 37.55, lng: 127.05 } }, c, {})[0], 'fail');
  assert.equal(evalCond(D2, {}, { geo: null }, c, {})[0], 'unknown');
  assert.equal(evalCond({ lines: null }, {}, { geo: { lat: 37.5, lng: 127 } }, c, {})[0], 'unknown');
  const a = await ask({ question: G.items.find(x => x.id === 'v2-sample4').q, today: TODAY, dataOpts: DO, profile: PROFILE });
  assert.ok(/경기남부는 이렇게 봤어요: 수원·성남·용인/.test(a.text), '경기남부 범위를 밝히지 않음');
  assert.ok(/신분당선 역세권/.test(a.text) && !/분당 ·/.test(a.text), "'신분당선'을 분당 지역으로 읽음");
});


// 사용자 샘플 5 (2026-10-04): 보유 계획 — 실거주 의무가 '몇 년 뒤 팔기'보다 길면 어렵다, 재당첨 제한이 있으면 청약으로 갈아타기 어렵다
test('샘플 5 — 보유 계획과 실거주 의무·재당첨 제한', async () => {
  const { planLine } = await import('../answer.mjs');
  const C = { plan: { sell_after: 5 } };
  assert.match(planLine({ limits: { duty: 0, rewin: 0 } }, C), /걸리지 않아요/);
  assert.match(planLine({ limits: { duty: 3, rewin: 10 } }, C), /그 안에 끝나요.*10년 동안 다른 청약 당첨이 막혀/);
  assert.match(planLine({ limits: { duty: 5, rewin: 0 } }, { plan: { sell_after: 3 } }), /실거주 의무\(5년\)가 더 길어/);
  assert.match(planLine({ limits: { duty: null, rewin: null } }, C), /공고문에서 확인/);
  assert.equal(planLine({ limits: {} }, {}), null);
  const a = await ask({ question: G.items.find(x => x.id === 'v2-sample5').q, today: TODAY, dataOpts: DO, profile: PROFILE });
  assert.ok(/비교할 단지: 프라이어팰리스, 고덕센트럴푸르지오, 삼익그린2차$/m.test(a.text), '단지 이름 자르기');
  assert.ok(/보유 계획\(5년 뒤 갈아타기 \/ 10년 이상 장기 보유\)/.test(a.text), '보유 계획을 받아 주지 않음');
  assert.ok(!/급지·호재/.test(a.text), "'상급지'를 급지로 읽음");
});
