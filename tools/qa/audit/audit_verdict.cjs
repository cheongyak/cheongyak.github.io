// 블라인드 감사 사례 (2026-10-02, 변경분: 일반 0세대 주택형 공통 조건·공공임대). 공고 6개 × 설계한 조건 6개 = 36건.
// cases.json(검토자용, 앱 판정 없음)과 app.json(앱 eligBucket·카드 문구)을 따로 쓴다. 사용: NODE_PATH=... node tools/qa/audit/audit_verdict.cjs <출력폴더>
const { chromium } = require('playwright'); const { readFileSync, existsSync, writeFileSync } = require('node:fs'); const { join, extname } = require('node:path');
const ROOT = join(__dirname, '../../..'), DOCS = join(ROOT, 'docs'), OUT = process.argv[2];
const LIST = { '2026000414-059.9700G': ['인천', '계양구'], '2026000414-084.9900B': ['인천', '계양구'], '2026930036-084.7450D': ['경기', '과천시'],
  '2026930035-084.7621A': ['충북', '청주시'], '2026930031-059.9979A': ['경기', '광명시'], '2026000307-055.0000A': ['경기', '군포시'] };
(async () => {
  const rental = JSON.parse(readFileSync(join(ROOT, 'tests/judge/listings.json'), 'utf8')).find(x => x.id === '2026000307-055.0000A');
  const b = await chromium.launch({ executablePath: existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined }); const page = await b.newPage();
  await page.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'qa.local') return r.abort();
    const f = join(DOCS, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1))); if (!existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ status: 200, body: readFileSync(f), contentType: { '.html':'text/html', '.json':'application/json' }[extname(f)] || 'application/octet-stream' }); });
  await page.goto('http://qa.local/', { waitUntil: 'networkidle' }); await page.waitForTimeout(400);
  const res = await page.evaluate(({ LIST, rental }) => {
    LISTINGS.push(fromApi(rental));
    const base = { household:'head', headSince:'2015-01-01', selfOwn:false, spouseOwn:false, hhHomes:'0', hhNeverOwned:true, win5y:false, recentWin:false, everWin:'none',
      acctType:'all', acctSince:'2014-01-01', acctAmount:1500, acctCount:120, acctPaid:2000, birth:'1990-03-01', sidoOwnSince:'2015-01-01', sidoSince:'2015-01-01', areaSince:'2015-01-01',
      eldersOnDeed:0, elder65:false, taxYears5:true, carValue:1000, realEstate:0, cash:3000, liquid:0, deposit:0, townInsurance:0, townFinOther:0, townOtherAsset:0, townDebt:0 };
    const P = (home) => [
      ['지역 거주·신혼(2023 혼인)·2025년생 자녀·외벌이 연 5,000만', { ...base, homeSido: home[0], homeSigun: home[1], married:true, marriedOn:'2023-05-01', dependents:2, kidsMinor:1, kidsOnDeed:1, youngestBirth:'2025-06-01', pregnant:false, hhSize:3, income:5000, spouseIncome:0, hhIncomeYear:5000 }],
      ['다른 지역(부산) 거주·나머지 위와 같음', { ...base, homeSido:'부산', homeSigun:'해운대구', married:true, marriedOn:'2023-05-01', dependents:2, kidsMinor:1, kidsOnDeed:1, youngestBirth:'2025-06-01', pregnant:false, hhSize:3, income:5000, spouseIncome:0, hhIncomeYear:5000 }],
      ['사는 곳 미입력·나머지 위와 같음', { ...base, homeSido:'', homeSigun:'', married:true, marriedOn:'2023-05-01', dependents:2, kidsMinor:1, kidsOnDeed:1, youngestBirth:'2025-06-01', pregnant:false, hhSize:3, income:5000, spouseIncome:0, hhIncomeYear:5000 }],
      ['지역 거주·본인 주택 1채', { ...base, homeSido: home[0], homeSigun: home[1], selfOwn:true, hhHomes:'1', hhNeverOwned:false, married:true, marriedOn:'2023-05-01', dependents:2, kidsMinor:1, kidsOnDeed:1, youngestBirth:'2025-06-01', pregnant:false, hhSize:3, income:5000, spouseIncome:0, hhIncomeYear:5000, realEstate:30000 }],
      ['지역 거주·미혼 1인 가구·연 4,000만·자녀 없음', { ...base, homeSido: home[0], homeSigun: home[1], married:false, marriedOn:'', dependents:0, kidsMinor:0, kidsOnDeed:0, youngestBirth:'', pregnant:false, hhSize:1, income:4000, spouseIncome:0, hhIncomeYear:4000 }],
      ['지역 거주·맞벌이 연 2억(각 1억)·2019년생 자녀', { ...base, homeSido: home[0], homeSigun: home[1], married:true, marriedOn:'2016-05-01', dependents:2, kidsMinor:1, kidsOnDeed:1, youngestBirth:'2019-01-01', pregnant:false, hhSize:3, income:10000, spouseIncome:10000, hhIncomeYear:20000 }]];
    const cases = [], app = []; let n = 0;
    for (const [id, home] of Object.entries(LIST)) {
      const L = LISTINGS.find(x => x.id === id);
      for (const [desc, pr] of P(home)) {
        const cid = 'V' + String(++n).padStart(2, '0');
        S.profile = Object.assign({}, DEFAULT_PROFILE, pr); save();
        cases.push({ id: cid, notice_id: id.split('-')[0], house_type: id.split('-')[1], area_m2: L.area, notice_date: L.notice, supply_category: L.category === 'remainder' ? '무순위·재공급(사후접수)' : '일반분양', case: desc, profile: pr });
        app.push({ id: cid, bucket: eligBucket(L, S.profile), card: meLine(L).replace(/<[^>]+>/g, '') });
      }
    }
    return { cases, app };
  }, { LIST, rental });
  await b.close();
  writeFileSync(join(OUT, 'cases.json'), JSON.stringify(res.cases, null, 1) + '\n'); writeFileSync(join(OUT, 'app.json'), JSON.stringify(res.app, null, 1) + '\n');
  console.log(res.cases.length + '건');
})();
