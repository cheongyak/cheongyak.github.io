// 답변 검사기. AI 가 아니라 코드가 검사한다. 하나라도 걸리면 내보내지 않는다.
import { redact } from './redact.js';

const VERDICTS = ['가능', '불가', '확인 필요', '2순위만'];
const POS = /(신청(할|하실)\s*수\s*있|신청이\s*가능|가능해요|가능합니다|넣을\s*수\s*있|자격이\s*(돼요|됩니다|있어요|충분))/;
const NEG = /(불가|신청(할|하실)\s*수\s*없|자격이\s*(안\s*돼|없어요|없습니다)|넣을\s*수\s*없|신청이\s*어려)/;
const FORBIDDEN = [/무조건/, /꼭\s*넣으세요/, /당첨\s*(가능성|확률)이?\s*(높|크|많)/, /로또/, /강력\s*추천/, /100%\s*(당첨|가능)/];
const SP_NAMES = { newborn: '신생아', newlywed: '신혼부부', first: '생애최초', multichild: '다자녀', elder: '노부모' };

export function parseAnswer(raw) {
  if (raw && typeof raw === 'object') return raw;
  const s = String(raw || '').trim();
  const a = s.indexOf('{'), b = s.lastIndexOf('}');
  if (a < 0 || b < a) return null;
  try { return JSON.parse(s.slice(a, b + 1)); } catch (e) { return null; }
}

function texts(ans) {
  const out = [ans.conclusion, ...(ans.my_conditions || []), ...(ans.why || []).map(x => x && x.text), ...(ans.official || []).map(x => x && x.text), ...(ans.cautions || []), ans.ask];
  return out.filter(x => typeof x === 'string' && x.trim());
}

// 숫자 토큰: 1,234 / 5.37 / 114 등. 날짜 숫자는 허용 목록 쪽에서 풀어 둔다.
const NUM = /\d[\d,]*(?:\.\d+)?/g;
const toNum = t => parseFloat(String(t).replace(/,/g, ''));
const decimals = t => { const m = /\.(\d+)$/.exec(String(t).replace(/,/g, '')); return m ? m[1].length : 0; };

function allowedNumbers(sources) {
  const vals = new Set();
  for (const src of sources) {
    const s = String(src || '');
    for (const m of s.matchAll(/(\d{4})-(\d{2})-(\d{2})/g)) { vals.add(+m[1]); vals.add(+m[2]); vals.add(+m[3]); }
    for (const t of s.match(NUM) || []) vals.add(toNum(t));
  }
  for (let i = 0; i <= 5; i++) vals.add(i);   // 1순위·2건·3개 같은 세는 말
  return [...vals].filter(v => Number.isFinite(v));
}

function numberAllowed(token, allowed) {
  const t = toNum(token), d = decimals(token);
  const scales = [1, 1e4, 1e-4, 1e8, 1e-8, 100, 0.01];
  for (const v of allowed) for (const k of scales) {
    const x = v * k;
    if (Math.abs(Number(x.toFixed(d)) - t) < 1e-9) return true;
  }
  return false;
}

export function validate(raw, { engine, evidence, question }) {
  const flags = [];
  const ans = parseAnswer(raw);
  if (!ans || typeof ans.conclusion !== 'string') return { ok: false, flags: ['형식 오류: JSON 이 아니거나 conclusion 없음'], answer: null };

  // 1. 판정 값
  if (!VERDICTS.includes(ans.verdict)) flags.push('판정 값 없음');
  else if (ans.verdict !== engine.verdict) flags.push(`판정 불일치: 답 ${ans.verdict} / 엔진 ${engine.verdict}`);

  // 2. 결론 문장이 엔진 판정과 어긋나는가
  const c = ans.conclusion;
  if (engine.verdict === '가능' && NEG.test(c)) flags.push('결론이 엔진(가능)과 반대');
  if (engine.verdict === '불가' && POS.test(c)) flags.push('결론이 엔진(불가)과 반대');
  if (engine.verdict === '확인 필요') {
    if (!/확인/.test(c)) flags.push('확인 필요인데 결론에 \'확인\'이 없음');
    if (/(신청(할|하실)\s*수\s*있어요|가능해요|가능합니다)/.test(c) && !/(확인|만약|하면|다면)/.test(c)) flags.push('확인 필요를 가능으로 단정');
  }
  if (engine.verdict === '2순위만' && !/2순위/.test(c)) flags.push('2순위만인데 결론에 2순위가 없음');

  // 3. 특별공급 유형별 판정과 어긋나는가
  const all = texts(ans);
  for (const sp of engine.special || []) {
    const name = SP_NAMES[sp.type];
    if (!name) continue;
    for (const sent of all.join(' ').split(/(?<=[.!?요])\s+/)) {
      if (!sent.includes(name) || !/(특별공급|특공)/.test(sent)) continue;
      if (sp.v === '불가' && POS.test(sent) && !NEG.test(sent)) flags.push(`${name} 특공: 엔진은 불가인데 가능으로 씀`);
      if (sp.v === '가능' && NEG.test(sent) && !POS.test(sent)) flags.push(`${name} 특공: 엔진은 가능인데 불가로 씀`);
      if (sp.v === '확인 필요' && (POS.test(sent) || NEG.test(sent)) && !/확인/.test(sent)) flags.push(`${name} 특공: 확인 필요를 단정`);
    }
  }

  // 4. 금지 표현
  for (const re of FORBIDDEN) if (all.some(t => re.test(t))) flags.push('금지 표현: ' + re.source);

  // 5. 근거 번호
  const ids = new Set(evidence.map(e => e.id));
  for (const [field, need] of [['why', false], ['official', true]]) {
    for (const x of ans[field] || []) {
      const refs = (x && x.refs) || [];
      if (need && !refs.length) flags.push(`${field}: 근거 번호 없는 규정 문장`);
      for (const r of refs) if (!ids.has(r)) flags.push(`${field}: 없는 근거 번호 ${r}`);
    }
  }

  // 6. 숫자는 엔진·근거·질문에 있는 것만
  const allowed = allowedNumbers([JSON.stringify(engine), ...evidence.map(e => e.text), question]);
  for (const t of all) {
    // 2026.09.18 / 2026-09-18 / 2026/9/18 같은 날짜는 연·월·일 숫자로 나눠 본다
    const plain = t.replace(/\[[^\]]*가림\]/g, '').replace(/(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\.?/g, '$1 $2 $3');
    for (const tok of plain.match(NUM) || []) {
      if (!numberAllowed(tok, allowed)) flags.push('출처 없는 숫자: ' + tok);
    }
  }

  // 7. 개인정보를 다시 쓰지 않았는가
  if (all.some(t => redact(t).found.length)) flags.push('개인정보 노출');

  return { ok: flags.length === 0, flags: [...new Set(flags)], answer: ans };
}
