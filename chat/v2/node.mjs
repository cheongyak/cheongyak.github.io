// Node 에서 쓰는 입구: docs/ 데이터를 읽어 한 번만 묶어 두고 ask 를 부른다 (CLI·시험·나중에 Actions 평가)
import { loadData } from './node-data.mjs';
import { ask as askWith } from './index.mjs';

let CACHE = null;
export function data(opts = {}) {
  if (!CACHE || opts.fresh || opts.today !== CACHE.opts.today || opts.listings !== CACHE.opts.listings || opts.past !== CACHE.opts.past) CACHE = { D: loadData(opts), opts };
  return CACHE.D;
}
export async function ask({ today = null, dataOpts = {}, ...rest }) {
  return askWith({ D: data({ today, ...dataOpts }), ...rest });
}
export { loadData };
