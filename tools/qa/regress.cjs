// 화면 회귀 검사 (새 세션에서도 그대로 쓰는 도구)
// 1) 판정 비교: 기준 docs(보통 origin/main)와 작업 중 docs 의 판정을 프로필 5개 × 모든 주택형으로 비교 (점수·마진·상태·특공·판정)
// 2) 화면 훑기: 작업 중 docs 의 모든 화면(목록·상세·자금·인터뷰·문서 등)을 프로필 3개로 그려 오류를 센다
// 사용: bash tools/qa/regress.sh            (origin/main 과 비교)
//       node tools/qa/regress.cjs <기준 docs 폴더> <작업 docs 폴더>
// 의도한 판정 변경이 없으면 'verdict changes 0' 이고, 'errs 0' 이어야 한다.
const { chromium } = require('playwright');
const { readFileSync, existsSync } = require('node:fs');
const { join, extname, resolve } = require('node:path');
const OLD = resolve(process.argv[2] || 'docs'), NEW = resolve(process.argv[3] || 'docs');
const EXE = existsSync('/opt/pw-browsers/chromium') ? { executablePath: '/opt/pw-browsers/chromium' } : {};
const TYPES = { '.html':'text/html', '.json':'application/json', '.png':'image/png', '.js':'text/javascript', '.webmanifest':'application/manifest+json', '.txt':'text/plain' };
async function serve(page, dir) {   // 외부 접속 없이 폴더를 http://site.local/ 로 연다
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.hostname !== 'site.local') return route.abort();
    const f = join(dir, u.pathname === '/' ? 'index.html' : decodeURIComponent(u.pathname.slice(1)));
    if (!existsSync(f)) return route.fulfill({ status: 404, body: '' });
    route.fulfill({ status: 200, body: readFileSync(f), contentType: TYPES[extname(f)] || 'application/octet-stream' });
  });
}
const PROFILES = [
 {homeSido:'경기',homeSigun:'광명시',sidoOwnSince:'2015-01-01',areaSince:'2015-01-01',household:'head',headSince:'2015-01-01',selfOwn:false,married:true,marriedOn:'2021-05-01',spouseOwn:false,acctType:'all',acctSince:'2014-01-01',acctAmount:1500,acctCount:60,acctPaid:1500,hhHomes:'0',win5y:false,recentWin:false,birth:'1988-03-01',dependents:2,kidsMinor:1,pregnant:false,youngestBirth:'2022-06-01',hhSize:3,income:7000,spouseIncome:0,realEstate:0,carValue:0,hhNeverOwned:true,taxYears5:true,elder65:false,cash:30000},
 {homeSido:'서울',sidoOwnSince:'2010-01-01',household:'head',headSince:'2012-01-01',selfOwn:false,married:true,marriedOn:'2012-01-01',spouseOwn:false,acctType:'all',acctSince:'2008-01-01',acctAmount:1500,acctCount:150,acctPaid:2000,hhHomes:'0',win5y:false,recentWin:false,birth:'1980-01-01',dependents:4,kidsMinor:3,kidsUnder6:1,gen3:false,pregnant:false,youngestBirth:'2021-01-01',hhSize:5,income:9000,spouseIncome:4000,hhIncomeYear:13000,realEstate:5000,carValue:2000,hhNeverOwned:true,taxYears5:true,elder65:false,cash:50000},
 {homeSido:'인천',sidoOwnSince:'2019-01-01',household:'member',selfOwn:false,married:false,acctType:'all',acctSince:'2023-01-01',acctAmount:300,acctCount:20,hhHomes:'0',win5y:false,recentWin:false,birth:'1996-01-01',dependents:0,kidsMinor:0,pregnant:false,hhSize:1,income:4000,realEstate:0,carValue:0,hhNeverOwned:true,taxYears5:false,elder65:false,cash:5000},
 {homeSido:'부산',sidoOwnSince:'2000-01-01',household:'head',headSince:'2000-01-01',selfOwn:true,married:true,marriedOn:'2000-01-01',spouseOwn:false,acctType:'deposit',acctSince:'2000-01-01',acctAmount:600,hhHomes:'1',win5y:false,recentWin:false,birth:'1970-01-01',dependents:2,kidsMinor:0,pregnant:false,hhSize:3,income:8000,spouseIncome:3000,realEstate:40000,carValue:3000,hhNeverOwned:false,taxYears5:true,elder65:true,cash:80000},
 {},
];
async function collect(url){
 const b=await chromium.launch(EXE);const p=await b.newPage();await serve(p,url);const errs=[];p.on('pageerror',x=>errs.push(x.message));
 await p.goto('http://site.local/',{waitUntil:'networkidle'});await p.waitForTimeout(600);
 const r=await p.evaluate(PROFILES=>{const out={};
  PROFILES.forEach((pr,pi)=>{const P=Object.assign({},DEFAULT_PROFILE,pr);syncHome(P);
   LISTINGS.forEach(L=>{const e=eligibility(L,P);const k=pi+'|'+L.id;
     const items=e.items.map(i=>i.k+'='+i.s+':'+i.v).join(';');
     const sp=spTypesFor(L).map(t=>{const r=spJudge(L,P,t);return t+':'+r.s+':'+(r.stage&&r.stage[0])+':'+r.fail.join('/')+':'+r.warn.join('/')}).join(',');
     const sc=myScore(L,P);const m=grade(L);
     out[k]={verdict:(e.ok?(e.unsure?'U':'OK'):e.rank2?'R2':'NO'),items,sp,score:sc.total+'/'+sc.parts.map(x=>x.v).join(','),margin:[m.g,m.lo==null?null:m.lo.toFixed(6),m.hi==null?null:m.hi.toFixed(6),m.tax.toFixed(6)].join(','),status:statusOf(L)};});});
  return out;},PROFILES);
 await b.close();return {r,errs};}
const rich = { homeSido:'경기', homeSigun:'성남시', sidoOwnSince:'2010-01-01', areaSince:'2025-06-01', sidoSince:'2010-01-01', household:'head', headSince:'2015-01-01', selfOwn:false, married:true, spouseOwn:false, marriedOn:'2022-05-01', income:9500, spouseIncome:9500, spouseLoan:0, cash:30000, liquid:5000, deposit:10000, loanMonthly:50,
  acctType:'all', acctSince:'2016-01-01', acctAmount:1500, acctCount:60, acctPaid:1500, recentWin:false, hhHomes:'0', win5y:false, birth:'1990-01-01', dependents:2, kidsMinor:1, youngestBirth:'2025-03-01', pregnant:false, realEstate:0, carValue:2000, hhNeverOwned:true, taxYears5:true, elder65:false, kidsUnder6:1, gen3:false, firstTime:true, kidsOnDeed:1, eldersOnDeed:0 };
async function sweep(dir){
const b=await chromium.launch(EXE);
const p=await b.newPage({viewport:{width:390,height:900}}); const errs=[]; p.on('pageerror',e=>errs.push(e.message)); await serve(p,dir);
await p.goto('http://site.local/',{waitUntil:'networkidle'}); await p.waitForTimeout(800);
const texts = await p.evaluate((rich)=>{ const out=[]; const grab=(tag)=>{ app.querySelectorAll('details').forEach(d=>d.open=true); out.push([tag, app.innerText]); };
  const profs = { empty:null, rich, partial:{ homeSido:'서울', household:'parents', parents60:true, parentsOwn:true, selfOwn:false, married:false, cash:5000 } };
  for (const [pn, pr] of Object.entries(profs)) {
    try { localStorage.clear(); } catch(e){}
    S.profile = Object.assign({}, DEFAULT_PROFILE, pr || {}); if (pr) save();
    S.id=null; S.sheet=null; go('feed'); grab(pn+'|feed');
    for (const v of ['grades','me','about','story','terms','privacy','alerts','trend']) { if (VIEWS[v]) { try { go(v); grab(pn+'|'+v); } catch(e) { out.push([pn+'|'+v,'ERROR '+e.message]); } } }
    for (const L of LISTINGS) { S.id=L.id; try { go('detail'); grab(pn+'|detail|'+L.id); if (VIEWS.plan) { go('plan'); grab(pn+'|plan|'+L.id); } } catch(e) { out.push([pn+'|detail|'+L.id,'ERROR '+e.message]); } }
    if (pn==='rich') { const n=visibleSteps().length; for (let i=0;i<n;i++){ S.step=i; go('onboard'); grab(pn+'|onboard|'+i); } }
    for (const k of ['now','fresh','closing']) { S.sheet=k; go('feed'); grab(pn+'|sheet|'+k); S.sheet=null; }
  }
  return out; }, rich);
const bad = texts.filter(x => String(x[1]).startsWith('ERROR'));
console.log('pages', texts.length, 'errs', errs.length + bad.length, errs.slice(0,3), bad.slice(0,3).map(x=>x[0]+' '+String(x[1]).slice(0,120)));
await b.close(); return errs.length + bad.length;}
(async()=>{const A=await collect(OLD),B=await collect(NEW);
 const keys=Object.keys(A.r);let diff={verdict:[],items:0,sp:0,score:0,margin:0,status:0};
 const why={};
 for(const k of keys){const a=A.r[k],b=B.r[k];if(!b){console.log('missing',k);continue;}
  for(const f of ['score','margin','status','sp']) if(a[f]!==b[f]){diff[f]++; if(diff[f]<=3) console.log('DIFF',f,k,'\n  old',a[f].slice(0,300),'\n  new',b[f].slice(0,300));}
  if(a.items!==b.items) diff.items++;
  if(a.verdict!==b.verdict){diff.verdict.push(k+' '+a.verdict+'→'+b.verdict);}
 }
 console.log('combos',keys.length,'score',diff.score,'margin',diff.margin,'status',diff.status,'sp',diff.sp,'items',diff.items,'verdict changes',diff.verdict.length);
 // classify verdict changes
 const cls={};diff.verdict.forEach(v=>{const [pi,id]=v.split(' ')[0].split('|');const L=id.slice(0,10);const key=pi+' '+L+' '+v.split(' ').slice(1).join(' ');cls[key]=(cls[key]||0)+1;});console.log(cls);
 console.log('errs',A.errs,B.errs);
 const n = await sweep(NEW);
 if (diff.verdict.length || n || A.errs.length || B.errs.length) process.exitCode = 1;
})();
