// AI 답이 검사기에 두 번 막히거나, AI 를 부를 수 없을 때 쓰는 고정 문구 답. 엔진 결과만으로 만든다.
const ASK = [
  [/거주/, '어느 시·도, 시·군·구에 사시는지 알려 주세요.'],
  [/무주택/, '세대원 모두 집(분양권 포함)이 없나요?'],
  [/세대주/, '세대주이신가요?'],
  [/통장/, '청약통장 종류와 가입일을 알려 주세요.'],
  [/소득/, '세대원 전체의 작년 소득과 가구원 수를 알려 주세요.'],
  [/자산/, '부동산과 자동차 가액을 알려 주세요(없으면 0).'],
  [/혼인|신혼/, '혼인신고일과 막내 자녀 생년월일을 알려 주세요.'],
  [/당첨/, '최근 5년 안에 세대원 중 청약에 당첨된 적이 있나요?'],
];

const CONCLUSION = {
  '가능': '지금 넣은 조건으로는 이 주택형에 신청할 수 있어요.',
  '불가': '지금 넣은 조건으로는 이 주택형에 신청할 수 없어요.',
  '확인 필요': '몇 가지를 더 확인해야 판정할 수 있어요.',
  '2순위만': '1순위 요건은 채우지 못했지만 2순위로는 신청할 수 있어요.',
};

export function askFor(engine) {
  const a = (engine.items || []).find(i => i.s === 'warn' && i.cause === 'A');
  if (!a) return null;
  for (const [re, q] of ASK) if (re.test(a.k)) return q;
  return `${a.k} 정보를 알려 주세요.`;
}

export function fallbackAnswer({ engine, evidence, intent }) {
  const items = engine.items || [];
  const evOf = k => (evidence.find(e => e.kind === 'engine' && e.title === '청약패스 판정: ' + k) || {}).id;
  const why = items.filter(i => i.s === 'fail' || i.s === 'warn').slice(0, 4).map(i => ({ text: `${i.k}: ${i.v}${i.s === 'warn' ? ' (확인 필요)' : ''}`, refs: [evOf(i.k)].filter(Boolean) }));
  const notices = evidence.filter(e => e.kind === 'notice');
  const seen = new Set();
  const official = notices.filter(e => !seen.has(e.tag) && seen.add(e.tag)).slice(0, 2).map(e => ({ text: `모집공고문의 '${e.tag}' 관련 조항을 확인하세요.`, refs: [e.id] }));
  const d = (engine.listing && engine.listing.dates) || {};
  let conclusion = CONCLUSION[engine.verdict] || '판정 결과를 확인해 주세요.';
  if (intent === 'schedule' && d.apply) conclusion = `일정은 접수 ${d.apply}${d.applyEnd && d.applyEnd !== d.apply ? '~' + d.applyEnd : ''}, 당첨자 발표 ${d.winner || '공고문 확인'}이에요. ` + conclusion;
  if (intent === 'docs') conclusion = '필요 서류는 모집공고문의 제출 서류 항목에서 확인하세요. ' + conclusion;
  return {
    verdict: engine.verdict,
    conclusion,
    my_conditions: items.filter(i => i.s === 'ok').slice(0, 3).map(i => `${i.k}: ${i.v}`),
    why,
    official,
    cautions: ['청약 자격은 모집공고일 기준이에요.'],
    ask: askFor(engine),
  };
}
