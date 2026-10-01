// AI 로 보내기 전에 개인정보를 가린다. 가린 종류만 돌려주고 원래 값은 어디에도 남기지 않는다.
const RULES = [
  ['주민등록번호', /\b\d{6}\s*-\s*[1-8]\d{6}\b/g],
  ['전화번호', /\b01[016789][\s-]?\d{3,4}[\s-]?\d{4}\b/g],
  ['전화번호', /\b0\d{1,2}-\d{3,4}-\d{4}\b/g],
  ['이메일', /[\w.+-]+@[\w-]+\.[\w.-]+/g],
  ['동·호수', /\d{1,4}\s*동\s*\d{1,4}\s*호/g],
  // 계좌: 숫자-숫자-숫자 꼴. 날짜(2026-10-01)는 빼고 본다
  ['계좌번호', /\b(?!(?:19|20)\d{2}-\d{1,2}-\d{1,2}\b)\d{2,6}-\d{2,6}-\d{2,8}(?:-\d{1,4})?\b/g],
];

export function redact(text) {
  let out = String(text || '');
  const found = new Set();
  for (const [name, re] of RULES) {
    out = out.replace(re, () => { found.add(name); return `[${name} 가림]`; });
  }
  return { text: out, found: [...found] };
}
