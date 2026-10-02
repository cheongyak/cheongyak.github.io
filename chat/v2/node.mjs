// Node 에서 쓰는 입구: docs/ 데이터를 읽어 한 번만 묶어 두고 ask 를 부른다 (CLI·시험·나중에 Actions 평가)
import { loadData } from './node-data.mjs';
import { ask as askWith } from './index.mjs';

let CACHE = null;
export function data(opts = {}) {
  if (!CACHE || opts.fresh || opts.today !== CACHE.opts.today || opts.listings !== CACHE.opts.listings || opts.past !== CACHE.opts.past) CACHE = { D: loadData(opts), opts };
  return CACHE.D;
}
// 키가 환경 변수에 있으면 출퇴근 시간을 실제로 조회 (Actions·서버). 로컬에 키가 없으면 직선거리만
import { carTime } from './commute.mjs';
const KEYS = { ncpId: process.env.NCP_MAPS_CLIENT_ID, ncpSecret: process.env.NCP_MAPS_CLIENT_SECRET, kakao: process.env.KAKAO_REST_KEY };
export async function ask({ today = null, dataOpts = {}, ...rest }) {
  const commute = rest.commute !== undefined ? rest.commute : (KEYS.ncpId || KEYS.kakao ? (a, b) => carTime(a, b, KEYS) : null);
  return askWith({ D: data({ today, ...dataOpts }), ...rest, commute });
}
export { loadData };
