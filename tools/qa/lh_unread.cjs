// 임대 공고 '공고문에서 못 읽음' 전수검사 (2026-10-20 사용자 '임대공고에도 공고문에서 못읽는것들이 잇네 … 다시는 안뜨도록 전수검사해')
// 지금 임대 공고 전부(LH·SH) × 빈칸 없는 내 조건 몇 가지로 화면 판정(rentalJudge)을 돌려,
// 내가 답해서 풀 수 없는 '확인' 항목(답할 칸 q 없음) 중 공고문 쪽 원인(읽지 못함·모르는 계층·공고문 확인)을 모두 모은다.
//  - 결과 evidence/qa/lh-unread.json, 줄 '[검증·임대 공고문 못 읽음] 공고ID 계층: 문장'
//  - 허용 목록(tools/qa/lh_unread_allow.json: {"공고ID|문장 앞부분": "원문을 읽고 확인한 이유"})에 없는 것이 하나라도 있으면 종료 코드 1
//    → Actions 가 수집 알림 이슈로 알린다. 허용은 공고문 원문을 직접 읽어 '원문 자체가 모호·공고문 확인이 맞음'일 때만 넣는다.
// 사용: NODE_PATH=$(npm root -g) node tools/qa/lh_unread.cjs
const { chromium } = require('playwright');
const { readFileSync, writeFileSync, existsSync, mkdirSync } = require('node:fs');
const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../..'), DOCS = join(ROOT, 'docs');
const ALLOW_F = join(__dirname, 'lh_unread_allow.json');
const ALLOW = existsSync(ALLOW_F) ? JSON.parse(readFileSync(ALLOW_F, 'utf8')) : {};
// 공고문 쪽 원인 문장 (내 입력이 모자라서 묻는 '입력 필요'는 제외)
const NOTICE_SIDE = /읽지 못|못 읽|모르는 계층|판정하지 못|판정 못|공고문 확인|공고문에서 확인|공고문을 확인|잘못 적혀|알 수 없어요/;
(async () => {
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined });
  const page = await b.newPage({ viewport: { width: 390, height: 844 } });
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    let body = readFileSync(f);
    if (u.pathname === '/config.json') { const c = JSON.parse(body); c.features = Object.assign({}, c.features, { lh_rental: true }); body = JSON.stringify(c); }
    r.fulfill({ status: 200, body, contentType: { '.html': 'text/html', '.json': 'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' });
  await page.evaluate(() => new Promise(res => { loadRental(); const t = setInterval(() => { if (RENTAL) { clearInterval(t); res(); } }, 50); }));
  const found = await page.evaluate(NS_RE => {
    const RE = new RegExp(NS_RE);
    const base = { birth: '1993-05-01', married: false, marriedOn: '', selfOwn: false, spouseOwn: false, household: 'head', parentsOwn: false, hhHomes: '0',
      eldersOnDeed: 0, kidsOnDeed: 0, acctType: 'all', acctSince: '2015-01-01', acctCount: 60, hhSize: 2, kidsMinor: 0, hhIncomeYear: 3000, income: 3000, spouseIncome: 0,
      realEstate: 0, carValue: 0, cash: 1000, liquid: 0, deposit: 0, townInsurance: 0, townFinOther: 0, townOtherAsset: 0, townDebt: 0, youthAsset: 1000, pregnant: false,
      lhStudent: false, lhStudentIncome: false, lhHousingBenefit: false, lhSingleParent: false, lhHomeOutside: false, lhStartupRec: false, lhJobCriteria: false, lhJobIncome: false,
      lhLongWorker: false, lhMinorHead: false, lhPreWed: false, lhBirthKids: 0 };
    const profiles = [
      base,
      Object.assign({}, base, { married: true, marriedOn: '2023-01-01', hhSize: 3, kidsMinor: 1, youngestBirth: '2024-01-01', spouseIncome: 2000 }),
      Object.assign({}, base, { birth: '1955-01-01', hhSize: 1 }),
      Object.assign({}, base, { birth: '2004-04-01', hhSize: 1, lhStudent: true, hhIncomeYear: 0, income: 0 }),
      Object.assign({}, base, { lhHousingBenefit: true, hhIncomeYear: 1000 }),
    ];
    const out = [], info = [];
    for (const N of RENTAL.notices) {
      if (N.judge_type && (!N.terms || !(N.terms.groups || []).length)) out.push([N.id, '(공고)', '공고문에서 계층 기준을 읽지 못함', N.name]);
      if (N.terms && (N.terms.unknown_groups || []).length) info.push([N.id, N.terms.unknown_groups.join('·'), N.name]);
      const seen = new Set();
      for (const P0 of profiles) {
        const sido = (N.terms && N.terms.local && N.terms.local.sido) || ({ '서울특별시': '서울', '부산광역시': '부산', '경상남도': '경남', '전북특별자치도': '전북', '경기도': '경기', '강원특별자치도': '강원', '대구광역시': '대구', '인천광역시': '인천', '충청남도': '충남', '충청북도': '충북', '대전광역시': '대전', '광주광역시': '광주', '전라남도': '전남', '경상북도': '경북', '울산광역시': '울산', '세종특별자치시': '세종', '제주특별자치도': '제주' })[N.region] || '서울';
        const p = Object.assign({}, DEFAULT_PROFILE, P0, { homeSido: sido, homeSigun: (N.terms && N.terms.local && N.terms.local.sigun) || '' });
        p._set = Object.keys(P0);
        let J; try { J = rentalJudge(N, p); } catch (e) { out.push([N.id, '-', 'error ' + e.message]); continue; }
        for (const g of J.groups || []) for (const it of g.items || []) {
          if (it.s !== 'check' || (it.q && it.q.length) || !RE.test(it.t)) continue;
          const k = g.key + '|' + it.t; if (seen.has(k)) continue; seen.add(k);
          out.push([N.id, g.key, it.t, N.name]);
        }
      }
    }
    return { out, info, scanned: RENTAL.notices.length, judged: RENTAL.notices.filter(N => N.judge_type).length };
  }, NOTICE_SIDE.source);
  const info = found.info;
  const rows = found.out.map(([id, g, t, name]) => { const key = Object.keys(ALLOW).find(a => { const [aid, at] = a.split('|'); return aid === id && t.startsWith(at); });
    return { id, group: g, text: t, name, allowed: key ? ALLOW[key] : null }; });
  const bad = rows.filter(r => !r.allowed);
  for (const r of rows) console.log(`[검증·임대 공고문 못 읽음${r.allowed ? '·허용' : ''}] ${r.id} ${r.group}: ${r.text}${r.allowed ? ' — ' + r.allowed : ''}`);
  for (const [id, gs] of info) console.log(`[검증·임대 판정 안 하는 계층(참고)] ${id} ${gs} — 화면은 '이 서비스가 판정하지 않는 계층 — 공고문 확인'`);
  console.log(`[임대 공고문 못 읽음] 검사한 공고 ${found.scanned}건(판정 대상 ${found.judged}) · 걸린 공고 ${new Set(rows.map(r => r.id)).size}건 · 항목 ${rows.length} · 허용 ${rows.length - bad.length} · 고칠 것 ${bad.length} · 화면 오류 ${errs.length}`);
  mkdirSync(join(ROOT, 'evidence/qa'), { recursive: true });
  // 어느 데이터로 검사했는지 남긴다 — 검증 요약(tools/verify_status.py)은 지금 데이터와 다르면(LH·SH 수집이 그 뒤에 돈 경우) 이 결과를 셈하지 않는다 (2026-10-21)
  const stamp = f => { try { return JSON.parse(readFileSync(join(DOCS, f), 'utf8')).updated || null; } catch (e) { return null; } };
  const data = { lh: stamp('lh-rental.json'), sh: stamp('sh-rental.json') };
  writeFileSync(join(ROOT, 'evidence/qa/lh-unread.json'), JSON.stringify({ data, scanned: found.scanned, judged: found.judged, rows, info, bad: bad.length, errs }, null, 1) + '\n');
  await b.close();
  process.exit(bad.length || errs.length ? 1 : 0);
})();
