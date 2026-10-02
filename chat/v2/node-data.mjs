// Node 용 데이터 묶음: docs/ 의 화면 코드·공고 데이터·지난 공고를 읽는다 (시험·CLI·Actions). 브라우저에서는 browser.mjs.
import { createRequire } from 'node:module';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const HERE = dirname(fileURLToPath(import.meta.url));
const DOCS = join(HERE, '../../docs');

export function loadData({ docs = DOCS, today = null, listings = null, past = true } = {}) {
  const { loadEngine } = require('./engine.cjs');
  const eng = loadEngine({ docs, today, listings });
  const rawById = Object.fromEntries(eng.raw.map(x => [x.id, x]));
  let pastRows = [];
  const pj = join(docs, 'archive/past-judge.json');
  if (past && existsSync(pj)) {   // 지난 공고 (2026.6.15 이후 마감, 공고문까지 읽은 판정 자료) — 항상 '과거 공고'로 표시
    const d = JSON.parse(readFileSync(pj, 'utf8'));
    pastRows = d.items.filter(x => !rawById[x.id]).map(x => ({ L: eng.E.fromApi(x), raw: x, past: true }));
  }
  const pa = join(docs, 'archive/past.json');
  if (past && existsSync(pa)) {   // 그 밖의 지난 1년 공고 (청약홈 개요만 — 공고문 값이 없어 '그때 자격'은 판정하지 않음)
    const have = new Set(pastRows.map(r => r.L.id).concat(Object.keys(rawById)));
    const d = JSON.parse(readFileSync(pa, 'utf8'));
    pastRows = pastRows.concat(d.items.filter(x => !have.has(x.id) && x.status !== '예정' && (x.apply_end || x.apply || '') < eng.today)
      .map(x => ({ L: eng.E.fromApi(Object.assign({ special_units: null }, x)), raw: x, past: true, noJudge: true })));
  }
  const live = eng.LS.map(L => ({ L, raw: rawById[L.id] || {}, past: false }));
  return { eng, E: eng.E, today: eng.today, rows: live.concat(pastRows), profileOf: eng.profileOf };
}

