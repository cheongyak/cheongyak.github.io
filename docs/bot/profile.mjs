// 청약봇 '공고 찾기'(기능 bot_find, 2026-10-21): 질문 글에서 '내 조건' 칸으로 옮길 수 있는 값만 읽는다.
// 원칙: 글에 분명히 적힌 값만(추측·환산 안 함). 날짜가 필요한 칸(생년월일·통장 가입일·혼인신고일·무주택 시작일)은 'N년·N세'만으로 날짜를 지어내지 않고
// ask 목록으로 돌려 '내 조건에서 직접 입력'을 안내한다. 저장은 사용자가 '내 조건에 저장'을 눌렀을 때만(화면 botSaveProfile).
// 반환: { set: {칸: 값}, shown: [보여 줄 글], ask: [직접 입력해야 하는 것] }   — 돈 단위는 '내 조건'과 같은 만원
const SIDO = [['서울', /서울/], ['경기', /경기(?:도)?(?![가-힣]*(?:남부|북부)?\s?(?:대학|청))/], ['인천', /인천/], ['부산', /부산/], ['대구', /대구/], ['광주', /광주광역|광주시(?!\s?[가-힣]+구?\s?경기)|(?<!경기\s?)광주(?=\s?(?:거주|살|사는|에서 살))/],
  ['대전', /대전/], ['울산', /울산/], ['세종', /세종/], ['강원', /강원/], ['충북', /충북|충청북도/], ['충남', /충남|충청남도/], ['전북', /전북|전라북도/], ['전남', /전남|전라남도/],
  ['경북', /경북|경상북도/], ['경남', /경남|경상남도/], ['제주', /제주/]];
const KNUM = { 한: 1, 하나: 1, 둘: 2, 두: 2, 셋: 3, 세: 3, 넷: 4, 네: 4, 다섯: 5 };

// '7천' 7000 · '7,500만' 7500 · '1.2억' 12000 · '2억 5천' 25000 · '3억5천만' 35000 · '9000' 9000 (만원)
export function manwon(s) {
  const t = String(s || '').replace(/,/g, '').replace(/\s+/g, '');
  const m = t.match(/^(?:(\d+(?:\.\d+)?)억)?(?:(\d+(?:\.\d+)?)천)?(\d+)?(?:만원?|원)?$/);
  if (!m || !(m[1] || m[2] || m[3])) return null;
  const v = (m[1] ? parseFloat(m[1]) * 10000 : 0) + (m[2] ? parseFloat(m[2]) * 1000 : 0) + (m[3] ? +m[3] : 0);
  return Number.isFinite(v) && v > 0 ? Math.round(v) : null;
}
const AMT = String.raw`(\d[\d,.]*\s?억(?:\s?\d[\d,.]*\s?천)?(?:\s?\d[\d,]*\s?만)?|\d[\d,.]*\s?천(?:\s?만)?|\d[\d,]*\s?만(?:\s?원)?)`;
const fmt = v => v >= 10000 ? (v / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 2 }) + '억' : v.toLocaleString('ko-KR') + '만원';

export function parseProfile(q) {
  const t = ' ' + String(q || '').replace(/\s+/g, ' ') + ' ';
  const set = {}, shown = [], ask = [];
  const put = (k, v, label) => { if (v == null || k in set) return; set[k] = v; shown.push(label); };
  // 혼인
  if (/미혼|싱글|비혼|혼자\s?살|1인\s?가구|독신/.test(t)) put('married', false, '미혼');
  else if (/신혼|결혼\s?\d+\s?년|결혼했|기혼|부부|맞벌이|외벌이|아내|남편|와이프/.test(t) && !/예비\s?신혼|결혼\s?(예정|할|앞두)/.test(t)) put('married', true, '혼인 중');
  // 가구원 수
  let m = t.match(/(\d|한|두|세|네|다섯)\s?(?:인|명)\s?(?:가족|가구|세대)/);
  if (m) { const n = KNUM[m[1]] || +m[1]; if (n >= 1 && n <= 10) put('hhSize', n, n + '인 가구'); }
  // 자녀 (미성년으로 읽지 않음 — '아이 둘'은 대부분 미성년이지만 나이를 모르면 미성년 자녀 수 칸에 넣지 않는다)
  m = t.match(/(?:아이|자녀|애|아기)(?:가)?\s?(\d|한|하나|둘|두|셋|세|넷|네)\s?(?:명|이)?/) || t.match(/(\d|한|두|세|네)\s?(?:명의?\s?)?(?:아이|자녀|애)/);
  if (m) { const n = KNUM[m[1]] || +m[1]; if (n >= 1 && n <= 9) { shown.push('자녀 ' + n + '명'); ask.push('자녀 나이(미성년 자녀 수·막내 생년월일)'); } }
  // 소득 — 본인·배우자·합산을 나눈다. 월급은 세전/세후를 몰라 넣지 않는다
  m = t.match(new RegExp(String.raw`(?:부부\s?합산|합산|맞벌이\s?합산|둘이\s?합쳐)\s?(?:연봉|연\s?소득|소득)?\s?` + AMT));
  if (m) { const v = manwon(m[1]); if (v) put('hhIncomeYear', v, '부부 합산 연소득 ' + fmt(v)); ask.push('본인·배우자 소득을 나눠서(특별공급 판정은 각자 소득 칸을 써요)'); }
  else {
    m = t.match(new RegExp(String.raw`(?:내|제|본인|저는?)?\s?(?:연봉|연\s?소득|세전\s?연봉|세전\s?소득)\s?(?:은|는|이|이에요|이고|약|대략)?\s?` + AMT));
    if (m) { const v = manwon(m[1]); if (v && v < 100000) put('income', v, '본인 연소득 ' + fmt(v)); }
    m = t.match(new RegExp(String.raw`(?:아내|남편|배우자|와이프|신랑)\s?(?:는|은|도)?\s?(?:연봉|연\s?소득|소득)?\s?` + AMT));
    if (m) { const v = manwon(m[1]); if (v && v < 100000) put('spouseIncome', v, '배우자 연소득 ' + fmt(v)); }
  }
  if (/월급|월\s?\d[\d,]*\s?만/.test(t) && !('income' in set) && !('hhIncomeYear' in set)) ask.push('연소득(세전) — 월급은 세전·세후를 몰라 넣지 않았어요');
  // 현금·자산
  m = t.match(new RegExp(String.raw`(?:현금|가용\s?현금|예금|모은\s?돈|자기\s?자본|자본금)\s?(?:은|는|이|이고|약|대략)?\s?` + AMT));
  if (m) { const v = manwon(m[1]); if (v) put('cash', v, '현금·예금 ' + fmt(v)); }
  // 무주택 — '세대'가 적혀 있을 때만 세대 0채
  if (/무주택\s?세대|세대\s?(?:원\s?)?(?:전원\s?)?무주택|세대\s?무주택/.test(t)) { put('selfOwn', false, '본인 무주택'); put('hhHomes', '0', '세대 무주택'); }
  else if (/무주택/.test(t) && !/무주택\s?기간/.test(t.replace(/무주택\s?\d+\s?년/, ''))) put('selfOwn', false, '본인 무주택');
  if (/무주택\s?(?:기간\s?)?\d+\s?년|\d+\s?년\s?(?:째\s?)?무주택/.test(t)) ask.push('무주택이 된 날(무주택 기간 점수는 날짜로 계산해요)');
  if (/1주택|유주택|집이\s?(?:한\s?채\s?)?있|집\s?(?:한\s?채\s?)?(?:있|보유)/.test(t) && !/무주택/.test(t)) ask.push('주택을 가진 사람이 본인인지 세대원인지');
  // 사는 곳
  m = t.match(/([가-힣]{2,6})\s?(?:에|에서)?\s?(?:거주|살고|사는|살아요|삽니다|살아|거주중|거주 중)/);
  if (m) { const s = SIDO.find(([, re]) => re.test(m[1])); if (s) put('homeSido', s[0], s[0] + ' 거주'); }
  // 날짜가 필요한 칸
  if (/\d{2}\s?살|만\s?\d{2}\s?세|\d{2}\s?세|\d{2,4}\s?년생/.test(t)) ask.push('생년월일(나이 기준은 모집공고일이라 날짜가 필요해요)');
  if (/통장|청약\s?저축|주택\s?청약\s?종합/.test(t)) ask.push('청약통장 종류·가입일·납입 횟수');
  if (/결혼\s?\d+\s?년|신혼\s?\d+\s?년|\d+\s?년\s?차/.test(t) && set.married) ask.push('혼인신고일');
  return { set, shown, ask: [...new Set(ask)] };
}
