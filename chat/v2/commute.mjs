// 출퇴근 시간 조회 (STEP 0-7). 서버(청약봇 Worker·Actions)에서만 부른다 — 키는 비밀값에서만 읽고, 기록·답에 넣지 않는다.
// 자동차: 네이버 Directions 5 → 실패하면 카카오모빌리티 길찾기. 대중교통: 아직 정하지 않음(카카오 공개 REST 경로 미확인, ODsay 는 2안).
// 카카오 지도·로컬 API 결과는 저장(캐시)해 다시 쓰면 안 되고 실시간 호출만 허용된다(카카오맵 팀 답변, devtalk 151435) → 질문할 때 그때그때 부른다.
// 결과: { mode, min, km, src, at } 또는 { mode, error }. 직선거리로 시간을 만들어 내지 않는다.

const withTimeout = (p, ms = 6000) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('시간 초과')), ms))]);

export async function carNaver(from, to, { id, secret, fetchImpl = fetch } = {}) {
  if (!id || !secret) return { mode: 'car', error: '네이버 키 없음' };
  const u = `https://maps.apigw.ntruss.com/map-direction/v1/driving?start=${from.lng},${from.lat}&goal=${to.lng},${to.lat}&option=trafast`;
  try {
    const r = await withTimeout(fetchImpl(u, { headers: { 'x-ncp-apigw-api-key-id': id, 'x-ncp-apigw-api-key': secret } }));
    const j = await r.json();
    const s = j && j.route && j.route.trafast && j.route.trafast[0] && j.route.trafast[0].summary;
    if (!r.ok || !s) return { mode: 'car', error: '네이버 ' + r.status + ' ' + String((j && (j.message || (j.error && j.error.message))) || j.code || '').slice(0, 80) };
    return { mode: 'car', min: Math.round(s.duration / 60000), km: Math.round(s.distance / 100) / 10, src: '네이버 Directions 5 (실시간 교통)', at: new Date().toISOString() };
  } catch (e) { return { mode: 'car', error: '네이버 ' + e.message }; }
}

export async function carKakao(from, to, { key, fetchImpl = fetch } = {}) {
  if (!key) return { mode: 'car', error: '카카오 키 없음' };
  const u = `https://apis-navi.kakaomobility.com/v1/directions?origin=${from.lng},${from.lat}&destination=${to.lng},${to.lat}&priority=RECOMMEND`;
  try {
    const r = await withTimeout(fetchImpl(u, { headers: { Authorization: 'KakaoAK ' + key } }));
    const j = await r.json();
    const s = j && j.routes && j.routes[0] && j.routes[0].result_code === 0 && j.routes[0].summary;
    if (!r.ok || !s) return { mode: 'car', error: '카카오 ' + r.status + ' ' + String((j && (j.msg || j.message || (j.routes && j.routes[0] && j.routes[0].result_msg))) || '').slice(0, 80) };
    return { mode: 'car', min: Math.round(s.duration / 60), km: Math.round(s.distance / 100) / 10, src: '카카오모빌리티 길찾기', at: new Date().toISOString() };
  } catch (e) { return { mode: 'car', error: '카카오 ' + e.message }; }
}

// 카카오 키가 살아 있는지 (장소 검색 1회) — 대중교통 경로는 아님
export async function kakaoKeyword(query, { key, fetchImpl = fetch } = {}) {
  if (!key) return { error: '카카오 키 없음' };
  try {
    const r = await withTimeout(fetchImpl('https://dapi.kakao.com/v2/local/search/keyword.json?size=1&query=' + encodeURIComponent(query), { headers: { Authorization: 'KakaoAK ' + key } }));
    const j = await r.json();
    if (!r.ok) return { error: '카카오 로컬 ' + r.status + ' ' + String(j.message || j.msg || '').slice(0, 80) };
    const d = j.documents && j.documents[0];
    return d ? { name: d.place_name, lat: +d.y, lng: +d.x } : { error: '검색 결과 없음' };
  } catch (e) { return { error: '카카오 로컬 ' + e.message }; }
}

export async function carTime(from, to, keys, fetchImpl) {
  const a = await carNaver(from, to, { id: keys.ncpId, secret: keys.ncpSecret, fetchImpl });
  if (!a.error) return a;
  const b = await carKakao(from, to, { key: keys.kakao, fetchImpl });
  return b.error ? { mode: 'car', error: a.error + ' / ' + b.error } : b;
}
