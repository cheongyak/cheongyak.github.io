// 검색 검산용 '따로 옮긴 계산' (CLAUDE.md 4-7항과 같은 원칙: 기대값을 검사 대상 코드로 만들지 않는다).
// search.mjs 를 import 하지 않고 docs/listings.json 원자료 필드만 보고 필수 조건을 판정한다. 결과: 'pass' | 'fail' | 'unknown'.
const sp = s => String(s || '').replace(/\s+/g, '');

export function oracleRequired(x, c, today) {
  const v = c.value;
  const status = () => { const s = x.special_apply || x.apply, e = x.apply_end || x.apply; return s && today < s ? '접수 예정' : e && today > e ? '마감' : '접수 중'; };
  const inR = r => (!r.sido || x.sido === r.sido) && (r.district ? sp(x.district).includes(sp(r.district)) || (r.words || []).some(w => sp(x.address).includes(w)) : (r.words && r.words.length ? r.words.some(w => sp(x.address).includes(w) || sp(x.name).includes(w)) : true));
  switch (c.key) {
    case 'region_in': return v.some(inR) ? 'pass' : 'fail';
    case 'region_out': return v.some(inR) ? 'fail' : 'pass';
    case 'price_max': return x.price == null ? 'unknown' : x.price <= v + 1e-9 ? 'pass' : 'fail';
    case 'area': return x.area >= v.min && x.area <= v.max ? 'pass' : 'fail';
    case 'households_min': return !x.complex || x.complex.status !== '확인' ? 'unknown' : x.complex.households >= v ? 'pass' : 'fail';
    case 'not_single': return !x.complex ? 'unknown' : x.complex.single === 'no' ? 'pass' : x.complex.single === 'maybe' ? 'fail' : 'unknown';
    case 'rooms': return 'unknown';
    case 'status': return v.includes(status()) ? 'pass' : 'fail';
    case 'supply':
      if (v === 'remainder') return x.category === 'remainder' ? 'pass' : 'fail';
      if (v === 'town') return /신혼희망타운/.test(x.name) ? 'pass' : 'fail';
      if (v === 'public') return x.house_dtl === '국민' ? 'pass' : 'fail';
      if (v === 'private') return x.house_dtl === '민영' ? 'pass' : 'fail';
      return 'skip';   // 특별공급 유형은 화면 판정 함수(spTypesFor)를 거쳐야 해서 여기서 검산하지 않음
    default: return 'skip';
  }
}
export const liveStatus = (x, today) => { const s = x.special_apply || x.apply, e = x.apply_end || x.apply; return s && today < s ? '접수 예정' : e && today > e ? '마감' : '접수 중'; };
