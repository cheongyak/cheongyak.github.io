// 출퇴근 조회 실제 확인 (Actions chat-v2-probe.yml 에서만 — 키는 GitHub Secrets). 키 값은 출력·파일에 쓰지 않는다.
// 고정 쌍: 좌표가 정확한 지금 공고 단지 5곳 × 판교역·의왕역. 결과 → evidence/chat-v2/commute-probe.json
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { carNaver, carKakao, kakaoKeyword } from '../commute.mjs';
import { PLACES } from '../lexicon.mjs';

const keys = { ncpId: process.env.NCP_MAPS_CLIENT_ID, ncpSecret: process.env.NCP_MAPS_CLIENT_SECRET, kakao: process.env.KAKAO_REST_KEY };
const raw = JSON.parse(readFileSync('docs/listings.json', 'utf8')), rows = Array.isArray(raw) ? raw : raw.items;
const seen = new Set(), sites = [];
for (const x of rows) { const n = x.id.split('-')[0]; if (x.geo && x.geo.precision === 'exact' && !seen.has(n)) { seen.add(n); sites.push({ name: x.name, lat: x.geo.lat, lng: x.geo.lng }); } if (sites.length >= 5) break; }
const dests = [PLACES['판교역'], PLACES['의왕역']];
const out = { at: new Date().toISOString(), keys: { naver: !!(keys.ncpId && keys.ncpSecret), kakao: !!keys.kakao }, kakao_local: null, pairs: [] };
out.kakao_local = await kakaoKeyword('판교역', { key: keys.kakao });
out.kakao_local_more = await Promise.all(['구로구', '마포구', '가산디지털단지역', '삼성전자 수원사업장'].map(async w => ({ q: w, ...(await kakaoKeyword(w, { key: keys.kakao })) })));   // 직장 위치 말투 그대로 (2026-10-02 카카오맵 켠 뒤)
for (const s of sites) for (const d of dests) {
  const [n, k] = await Promise.all([carNaver(s, d, { id: keys.ncpId, secret: keys.ncpSecret }), carKakao(s, d, { key: keys.kakao })]);
  out.pairs.push({ from: s.name, to: d.name, naver_car: n, kakao_car: k });
}
const ok = p => !p.error;
out.summary = { pairs: out.pairs.length, naver_ok: out.pairs.filter(p => ok(p.naver_car)).length, kakao_ok: out.pairs.filter(p => ok(p.kakao_car)).length, kakao_local_ok: !out.kakao_local.error,
  transit: '대중교통은 아직 조회하지 않음 (카카오 공개 REST 경로 미확인 — 다음 단계에서 정함)' };
mkdirSync('evidence/chat-v2', { recursive: true });
writeFileSync('evidence/chat-v2/commute-probe.json', JSON.stringify(out, null, 1) + '\n');
console.log('[출퇴근 확인] 네이버 자동차 ' + out.summary.naver_ok + '/' + out.pairs.length + ' · 카카오 자동차 ' + out.summary.kakao_ok + '/' + out.pairs.length + ' · 카카오 장소 검색 ' + (out.summary.kakao_local_ok ? '됨' : '안 됨: ' + out.kakao_local.error));
out.pairs.slice(0, 4).forEach(p => console.log('  ', p.from.slice(0, 14), '→', p.to, '| 네이버', p.naver_car.error || p.naver_car.min + '분 ' + p.naver_car.km + 'km', '| 카카오', p.kakao_car.error || p.kakao_car.min + '분 ' + p.kakao_car.km + 'km'));
