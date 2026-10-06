// SH 블라인드 대조 (2026-10-06): profiles.json 을 앱 입력 칸으로 옮긴 값으로 화면 판정 엔진을 돌려 blind.json(공고문만 읽은 검토자)과 비교
// 사용: node evidence/audit/2026-10-06-sh/compare.cjs
const fs=require('fs'),vm=require('vm'),path=require('path');const R=path.join(__dirname,'../../..');
const html=fs.readFileSync(R+'/docs/index.html','utf8');const src=html.slice(html.lastIndexOf('<script>')+8,html.lastIndexOf('</script>'));
const dummy=new Proxy(function(){},{get:(t,k)=>k===Symbol.toPrimitive?()=>'':k==='length'?0:dummy,apply:()=>dummy,construct:()=>dummy,set:()=>true});
const store={};const ctx={console,Math,Date,JSON,Intl,Promise,Set,Map,Proxy,Number,String,Object,Array,RegExp,Symbol,Error,encodeURIComponent,decodeURIComponent,isNaN,parseFloat,parseInt,Infinity,NaN,URLSearchParams,document:dummy,navigator:{userAgent:'node'},location:{hash:'',pathname:'/',search:''},history:{state:null,replaceState(){},pushState(){}},localStorage:{getItem:k=>store[k]??null,setItem:(k,v)=>{store[k]=String(v)},removeItem:k=>{delete store[k]}},matchMedia:()=>({matches:false,addEventListener(){}}),addEventListener(){},removeEventListener(){},scrollTo(){},requestAnimationFrame(){},setTimeout,clearTimeout,confirm:()=>false,fetch:()=>new Promise(()=>{})};
ctx.window=ctx;ctx.globalThis=ctx;vm.createContext(ctx);vm.runInContext(src+`\n;globalThis.__E={rentalJudge,DEFAULT_PROFILE};`,ctx);const E=ctx.__E;
const G=JSON.parse(fs.readFileSync(R+'/tests/golden/sh_rental.json','utf8')).notices;
const N=s=>{const g=G.find(x=>x.seq===s);return {id:'SH-'+s,org:'SH',type:g.type,posted:g.posted,terms:g.terms,judge_type:true}};
const Z={townInsurance:0,townFinOther:0,townOtherAsset:0,townDebt:0,liquid:0,deposit:0,homeSido:'서울'};
const nw=(o)=>Object.assign({household:'head',selfOwn:false,spouseOwn:false,parentsOwn:false,hhHomes:'0',lhPreWed:false,lhSingleParent:false},Z,o);
// 앱 입력 칸 (총자산은 현금 칸에 넣고 자동차는 자동차 칸: 총자산 = 현금 + 자동차)
const A={
 A1:nw({married:true,marriedOn:'2020-03-15',birth:'1991-07-01',hhSize:2,hhIncomeYear:5600,income:5600,spouseIncome:0,kidsMinor:0,pregnant:false,cash:20000-1500,carValue:1500,realEstate:0}),
 A2:nw({married:true,marriedOn:'2021-06-01',birth:'1990-02-01',hhSize:3,hhIncomeYear:7600,income:4000,spouseIncome:3600,kidsMinor:1,youngestBirth:'2025-05-01',lhBirthKids:1,pregnant:false,cash:37000-3000,carValue:3000,realEstate:0}),
 A3:nw({married:false,birth:'1995-01-01',hhSize:2,hhIncomeYear:3500,income:3500,kidsMinor:1,youngestBirth:'2024-11-20',lhBirthKids:1,pregnant:false,shSupportSingle:null,lhSingleParent:true,cash:5000,carValue:0,realEstate:0}),
 A4:nw({married:true,marriedOn:'2016-01-01',birth:'1985-01-01',hhSize:3,hhIncomeYear:6000,income:6000,spouseIncome:0,kidsMinor:1,youngestBirth:'2019-08-01',lhBirthKids:0,pregnant:false,cash:9000,carValue:1000,realEstate:0}),
 A5:nw({married:true,marriedOn:'2023-01-01',birth:'1992-01-01',hhSize:3,hhIncomeYear:5000,income:5000,spouseIncome:0,kidsMinor:1,youngestBirth:'2024-12-01',lhBirthKids:1,pregnant:false,cash:20000-4800,carValue:4800,realEstate:0}),
 B1:nw({married:true,marriedOn:'2012-05-05',birth:'1984-01-01',hhSize:2,hhIncomeYear:13000,income:8000,spouseIncome:5000,kidsMinor:0,pregnant:false,cash:30000-7000,carValue:7000,realEstate:0}),
 B2:nw({married:true,marriedOn:'2024-02-01',birth:'1994-01-01',hhSize:2,hhIncomeYear:10000,income:10000,spouseIncome:0,kidsMinor:0,pregnant:false,cash:18000,carValue:2000,realEstate:0}),
 B3:nw({married:true,marriedOn:'2022-01-01',birth:'1990-01-01',hhSize:2,hhIncomeYear:8000,income:5000,spouseIncome:3000,kidsMinor:0,pregnant:false,spouseOwn:true,hhHomes:'1',cash:28000,carValue:2000,realEstate:0}),
 C1:Object.assign({married:false,birth:'1986-10-03',household:'head',hhSize:1,hhIncomeYear:5400,income:5400,selfOwn:false,hhHomes:'0',cash:10000,carValue:0,realEstate:0,kidsMinor:0,pregnant:false},Z),
 C2:Object.assign({married:false,birth:'1999-04-01',household:'parents',hhSize:3,hhIncomeYear:11000,income:2500,selfOwn:false,parentsOwn:true,hhHomes:'1',cash:28000,carValue:2000,realEstate:0,kidsMinor:0,pregnant:false},Z),
 C3:Object.assign({married:false,birth:'2000-01-01',household:'head',hhSize:1,hhIncomeYear:3000,income:3000,selfOwn:false,hhHomes:'0',cash:35000,carValue:0,realEstate:0,kidsMinor:0,pregnant:false},Z),
 C4:Object.assign({married:true,marriedOn:'2024-01-01',birth:'1995-01-01',household:'head',hhSize:2,hhIncomeYear:4000,income:4000,spouseIncome:0,selfOwn:false,spouseOwn:false,hhHomes:'0',cash:5000,carValue:0,realEstate:0,kidsMinor:0,pregnant:false},Z)};
const P=JSON.parse(fs.readFileSync(__dirname+'/profiles.json','utf8')),B=JSON.parse(fs.readFileSync(__dirname+'/blind.json','utf8'));
let diff=0;const rows=[];
for(const x of P){const p=Object.assign({},E.DEFAULT_PROFILE,A[x.id]);p._set=Object.keys(A[x.id]);const J=E.rentalJudge(N(x.notice),p);const b=B.find(y=>y.id===x.id).groups;
 for(const [k,v] of Object.entries(b)){const g=J.groups.find(g=>g.key===k);const a=g?g.s:'(없음)';const same=a===v||(['na','no'].includes(a)&&['na','no'].includes(v));if(!same)diff++;rows.push(`${x.id} ${k}: 앱 ${a} · 검토자 ${v}${same?'':'  ← 다름'}${!same&&g?' ['+g.items.filter(i=>i.s!=='ok').map(i=>i.t).join(' / ')+']':''}`);}}
console.log(rows.join('\n'));console.log(`다름 ${diff}건 (na·no 는 둘 다 '조건 밖'으로 같게 봄)`);
fs.writeFileSync(__dirname+'/compare.txt',rows.join('\n')+`\n다름 ${diff}건\n`);
