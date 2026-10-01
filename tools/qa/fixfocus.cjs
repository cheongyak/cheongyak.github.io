// 바로 답하기 표시 검사 (기능: fix_focus): 모든 버튼에서 빨간 칸(지금 판정에 필요한 질문)이 하나 이상 나오는지, 저장하면 접히는지. 사용: NODE_PATH=... node tools/qa/fixfocus.cjs
// 모든 '바로 답하기' 버튼: 빨간 칸이 하나 이상 있는지, 저장 후 패널이 닫히는지
const { chromium } = require('playwright'); const { readFileSync, existsSync } = require('node:fs'); const { join, extname } = require('node:path');
(async () => { const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }); const p = await b.newPage({ viewport:{width:390,height:844} }); const errs=[]; p.on('pageerror', e => errs.push(e.message));
  await p.route('**/*', r => { const u = new URL(r.request().url()); if (u.hostname !== 'j.local') return r.abort(); const f = join('docs', u.pathname === '/' ? 'index.html' : u.pathname.slice(1)); if (!existsSync(f)) return r.fulfill({status:404,body:''}); r.fulfill({ status: 200, body: readFileSync(f), contentType: extname(f)==='.html'?'text/html':'application/json' }); });
  await p.goto('http://j.local/', { waitUntil: 'networkidle' }); await p.waitForTimeout(400);
  const res = await p.evaluate(() => { const out = { opened:0, marked:0, noMark:{}, closed:0 };
    const profs = [{homeSido:'경기',homeSigun:'광명시',household:'head',selfOwn:false,married:true,acctType:'all'}, {homeSido:'서울',household:'parents',parents60:true,parentsOwn:true,selfOwn:false,married:false,acctType:''}, {homeSido:'인천',household:'head',selfOwn:false,married:true,marriedOn:'2015-01-01',kidsMinor:1,acctType:'all',acctSince:'2015-01-01',hhHomes:'1',everWin:'yes'}];
    for (const pr of profs) for (const L of LISTINGS.filter(x => !x.sample).slice(0, 60)) {
      S.profile = Object.assign({}, DEFAULT_PROFILE, pr); S.id = L.id; S.fix = null; go('detail');
      const keys = [...new Set([...document.querySelectorAll('[data-fix]')].map(x => x.dataset.fix))];
      for (const k of keys) { S.fix = { id:L.id, k, keys: fixKeysFor(k, L, S.profile) }; render(); out.opened++;
        if (document.querySelector('#fixpanel [data-fixneed]')) out.marked++; else out.noMark[k] = (out.noMark[k] || 0) + 1;
        fixSave(); if (!document.querySelector('#fixpanel')) out.closed++; } }
    return out; });
  console.log(JSON.stringify(res), 'errs', errs.slice(0,3)); await b.close(); })();
