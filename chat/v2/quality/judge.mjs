// AI 심사 — 코드 채점기(rubric.mjs)가 못 재는 '도움 됨·자연스러움·예시 수준인지'를 잰다.
//  ① 절대 평가: G-Eval(Liu 외 2023) 방식 — 채점표(항목별 정의 + 1~5점 기준)를 주고 항목마다 점수만 JSON 으로.
//  ② 짝 비교: MT-Bench / Chatbot Arena(Zheng 외 2023) 방식 — 같은 질문의 두 답 A·B 중 나은 쪽. 순서 편향을 없애려고 A·B 자리를 바꿔 두 번 묻고, 둘이 다르면 무승부.
//  ③ 순위: Bradley-Terry(=Elo 의 확률 모형)로 버전(답 틀·프롬프트)마다 실력값을 구해, 새 버전이 기존 버전을 이길 때만 채택(챔피언/도전자).
// 판정·숫자 정확성은 AI 심사에 맡기지 않는다 — 그건 checkAnswer(코드)가 치명 검사로 먼저 거른다.

export const CRITERIA = {
  이해: '질문자의 상황(가족·직장·예산·원하는 지역)과 조건을 정확히 짚었는가',
  결론: "첫머리에 '그래서 어디를 보면 되는지' 결론이 분명한가, 갈래가 있으면 갈래를 먼저 말했는가",
  근거: '후보마다 왜 이 곳인지 질문자 조건과 이어서 설명했는가 (숫자에 출처·추정 표시)',
  정직: '모르는 것(데이터 없음)을 모른다고 말하고, 추측을 사실처럼 쓰지 않았는가',
  도움: '다음에 할 일(대안·좁혀 줄 질문·알림)이 실제로 쓸모 있는가',
  말투: '해요체로 따뜻하지만 군더더기 없이 읽기 쉬운가 (휴대폰 화면 기준)',
};

export function absolutePrompt(question, answer) {
  const system = `너는 부동산 청약 상담 답변 심사위원이다. 아래 채점표로 답을 1~5점(5=사람 전문가 상담 수준, 3=쓸 만하지만 아쉬움, 1=도움 안 됨)으로 매긴다.
채점표:\n${Object.entries(CRITERIA).map(([k, v]) => '- ' + k + ': ' + v).join('\n')}
숫자가 맞는지는 따로 검사하니 신경 쓰지 말고, 위 항목만 본다. 답은 JSON 하나: {"scores":{"이해":n,...},"best":"가장 잘한 점 한 줄","fix":"가장 먼저 고칠 점 한 줄"}`;
  return { system, user: `질문: ${question}\n\n답:\n${answer}` };
}
export function parseAbsolute(text) {
  try { const j = JSON.parse(String(text).replace(/^```(json)?|```$/g, '').trim()); const sc = j.scores || {};
    if (!Object.keys(CRITERIA).every(k => Number.isFinite(sc[k]) && sc[k] >= 1 && sc[k] <= 5)) return null;
    return { scores: sc, mean: Object.values(sc).reduce((a, b) => a + b, 0) / Object.keys(CRITERIA).length, best: j.best || '', fix: j.fix || '' };
  } catch (e) { return null; }
}

export function pairPrompt(question, a, b) {
  const system = `너는 부동산 청약 상담 답변 심사위원이다. 같은 질문에 대한 두 답(A, B) 중 질문자에게 더 도움이 되는 쪽을 고른다.
기준: ${Object.entries(CRITERIA).map(([k, v]) => k + '(' + v + ')').join(' / ')}. 길이가 길다고 더 좋은 것이 아니다. 답은 JSON 하나: {"winner":"A"|"B"|"tie","why":"한 줄"}`;
  return { system, user: `질문: ${question}\n\n[답 A]\n${a}\n\n[답 B]\n${b}` };
}
const winnerOf = t => { try { const j = JSON.parse(String(t).replace(/^```(json)?|```$/g, '').trim()); return ['A', 'B', 'tie'].includes(j.winner) ? j : null; } catch (e) { return null; } };

// 자리를 바꿔 두 번 묻는다. 두 번 다 같은 답을 고르면 그 답이 이김, 엇갈리면 무승부 (자리 편향 제거)
export async function pairwise(llm, question, x, y) {
  const r1 = winnerOf(await llm({ ...pairPrompt(question, x.text, y.text), purpose: 'judge-pair' }));
  const r2 = winnerOf(await llm({ ...pairPrompt(question, y.text, x.text), purpose: 'judge-pair' }));
  const v1 = r1 ? (r1.winner === 'A' ? x.id : r1.winner === 'B' ? y.id : 'tie') : 'tie', v2 = r2 ? (r2.winner === 'A' ? y.id : r2.winner === 'B' ? x.id : 'tie') : 'tie';
  return { a: x.id, b: y.id, winner: v1 === v2 ? v1 : 'tie', why: [r1 && r1.why, r2 && r2.why].filter(Boolean).join(' / ') };
}

// Bradley-Terry: 이긴 횟수로 버전마다 실력값(평균 0). 무승부는 반 승. MM 반복법(Hunter 2004)
export function bradleyTerry(games, iters = 200) {
  const ids = [...new Set(games.flatMap(g => [g.a, g.b]))], p = Object.fromEntries(ids.map(i => [i, 1]));
  const w = Object.fromEntries(ids.map(i => [i, 0])), n = {};
  for (const g of games) { const k = [g.a, g.b].sort().join('|'); n[k] = (n[k] || 0) + 1; if (g.winner === 'tie') { w[g.a] += 0.5; w[g.b] += 0.5; } else w[g.winner] += 1; }
  for (let t = 0; t < iters; t++) {
    for (const i of ids) { let d = 0; for (const j of ids) { if (i === j) continue; const k = [i, j].sort().join('|'); if (n[k]) d += n[k] / (p[i] + p[j]); } if (d > 0) p[i] = Math.max(1e-6, w[i] / d); }
    const g = Math.exp(ids.reduce((s, i) => s + Math.log(p[i]), 0) / ids.length); ids.forEach(i => { p[i] /= g; });
  }
  return Object.fromEntries(ids.map(i => [i, { strength: Math.round(Math.log(p[i]) * 1000) / 1000, elo: Math.round(1000 + 400 * Math.log10(p[i])), wins: w[i] }]));
}
