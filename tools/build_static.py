"""검색엔진·광고 심사용 정적 페이지 만들기 (기능: static_pages)

앱은 한 페이지(docs/index.html)에서 화면을 바꾸는 구조라 검색엔진·광고 심사 크롤러가 문서 내용을 잘 못 읽는다.
그래서 문서 화면과 청약 기준 가이드를 별도 주소의 일반 HTML 페이지로 만든다.
  - /story/ /about/ /terms/ /privacy/ /updates/ : 앱 화면 그대로 (tools/snapshot_docs.cjs 가 그린 조각)
  - /guide/ /guide/income/ /guide/score/ /guide/deposit/ : 모집공고문 원문 표에서 뽑은 기준표 (공고문 대조로 앱 수치와 같음이 검증된 숫자)
  - docs/sitemap.xml 갱신
실행: node tools/snapshot_docs.cjs && python -m tools.build_static
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import notice_pdf
from tools.make_judge_cases import PUB, MIN, amt, score

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SITE = "https://cheongyakpass.kr"
NOTICE = ROOT / "evidence" / "notices"
TODAY = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
APPLYHOME = "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo={0}&pblancNo={0}"


def style() -> str:
    s = (DOCS / "index.html").read_text(encoding="utf-8")
    return re.search(r"<style>(.*?)</style>", s, re.S).group(1)


NAV = [("/", "공고 보기"), ("/guide/", "청약 기준 가이드"), ("/about/", "이용 안내"), ("/updates/", "업데이트 내역"), ("/privacy/", "개인정보처리방침")]


def page(slug: str, title: str, desc: str, body: str) -> str:
    url = f"{SITE}/{slug}" if slug else SITE + "/"
    nav = " · ".join(f'<a href="{h}">{t}</a>' for h, t in NAV)
    foot = " · ".join(f'<a href="{h}">{t}</a>' for h, t in NAV + [("/story/", "만든 이유"), ("/terms/", "이용약관")])
    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} | 청약패스</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article"><meta property="og:site_name" content="청약패스"><meta property="og:locale" content="ko_KR">
<meta property="og:url" content="{url}"><meta property="og:title" content="{html.escape(title)} | 청약패스"><meta property="og:description" content="{html.escape(desc)}">
<meta property="og:image" content="{SITE}/og.png">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">
<style>{style()}
.static-wrap{{max-width:720px;margin:0 auto;padding:16px 16px 48px}} .static-nav{{font-size:14px;margin:4px 0 14px;line-height:1.8}} .static-nav a{{white-space:nowrap}}
.static-brand{{font-size:20px;font-weight:800;text-decoration:none;color:inherit}} .gtbl{{width:100%;border-collapse:collapse;font-size:13px}} .gtbl th,.gtbl td{{padding:6px 5px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}
.gtbl th:first-child,.gtbl td:first-child{{text-align:left}} .gwrap{{overflow-x:auto}} .static-foot{{margin-top:24px;font-size:13px;line-height:1.9;color:var(--muted)}}
</style>
</head><body>
<div class="static-wrap">
<header><a class="static-brand" href="/">청약패스</a> <span class="beta">베타</span><nav class="static-nav">{nav}</nav></header>
<div class="betabar" role="note"><b>베타 · 참고용</b><span>이 사이트의 판정과 기준표는 공개 자료로 만든 참고용이에요. 신청 전 <b>모집공고문</b>과 <b>청약홈 청약자격 확인</b>으로 꼭 확인하세요.</span></div>
<main>
{body}
</main>
<footer class="static-foot">{foot}<br>청약패스는 청약홈(한국부동산원)·LH·국토교통부와 관계없는 개인이 운영해요. 페이지 생성 {TODAY}</footer>
</div>
</body></html>
"""


def won(v: int) -> str:
    return f"{v:,}"


def notice_link(no: str, name: str) -> str:
    return f'<a href="{APPLYHOME.format(no)}" target="_blank" rel="noopener">{html.escape(name)} 모집공고 ({no})</a>'


def guide_income() -> str:
    pub = notice_pdf.notice_facts((NOTICE / "2026000414.txt").read_text(encoding="utf-8"))["income_rows"]
    town = notice_pdf.notice_facts((NOTICE / "2026820010.txt").read_text(encoding="utf-8"))["income_rows"]
    rows = {**town, **pub}
    tr = "".join(f"<tr><td>{p}%</td>{''.join(f'<td>{won(v)}</td>' for v in rows[p])}</tr>" for p in sorted(rows, key=int))
    stages = lambda d, dual=True: "".join(
        f"<tr><td>{n}</td><td>{a}%</td><td>{b if b else '-'}{'%' if b else ''}</td></tr>" for n, a, b in d)
    return f"""<h1>2026년 청약 소득 기준표</h1>
<p class="muted small">2025년도 도시근로자 가구원수별 가구당 월평균소득 기준 · 2026년 모집공고문 원문 표 · 마지막 대조 {TODAY}</p>
<section class="card doc"><h2>월평균소득 금액표 (원)</h2>
<p>특별공급(신생아·신혼부부·생애최초·다자녀·노부모부양), 공공분양 일반공급(전용 60㎡ 이하), 신혼희망타운은 세대의 <b>월평균소득</b>이 아래 금액 이하여야 해요.
가구원수는 무주택세대구성원 전원(태아 포함)이고, 9인 이상은 8인 금액에 1인당 579,278원(100% 기준)을 더해요.</p>
<div class="gwrap"><table class="gtbl"><thead><tr><th>기준</th><th>3인 이하</th><th>4인</th><th>5인</th><th>6인</th><th>7인</th><th>8인</th></tr></thead><tbody>{tr}</tbody></table></div>
<p class="small muted">출처: {notice_link('2026000414', '인천계양지구 A6블록 공공분양')}, {notice_link('2026820010', '인천계양 A17블록 신혼희망타운')} 소득 기준 표. 청약패스는 매일 수집한 모든 모집공고문의 이 표를 앱 계산값과 자동 대조해요.</p></section>
<section class="card doc"><h2>공공분양 특별공급 단계별 기준 (LH 공고문 기준)</h2>
<p>소득에 맞는 첫 단계부터 경쟁하고, 떨어지면 다음 단계로 자동으로 넘어가요. 맞벌이는 본인과 배우자 모두 근로·사업소득이 있는 경우예요.</p>
<div class="gwrap"><table class="gtbl"><thead><tr><th>신생아 특별공급</th><th>외벌이</th><th>맞벌이</th></tr></thead><tbody>{stages(PUB['newborn'])}</tbody></table></div>
<div class="gwrap"><table class="gtbl"><thead><tr><th>신혼부부·생애최초</th><th>외벌이</th><th>맞벌이</th></tr></thead><tbody>{stages(PUB['newlywed'])}</tbody></table></div>
<div class="gwrap"><table class="gtbl"><thead><tr><th>다자녀가구</th><th>외벌이</th><th>맞벌이</th></tr></thead><tbody>{stages(PUB['multichild'])}</tbody></table></div>
<div class="gwrap"><table class="gtbl"><thead><tr><th>노부모부양</th><th>외벌이</th><th>맞벌이</th></tr></thead><tbody>{stages(PUB['elder'])}</tbody></table></div>
<p><b>출산가구 완화:</b> 2023.3.28 이후 태어난 자녀(태아 포함)가 1명이면 소득 기준이 10%p, 2명 이상(그 뒤 출생 1명 + 그 전 출생 자녀 포함)이면 20%p 올라가요.
자산 기준도 부동산 2억 1,550만원 → 2억 3,705만원·2억 5,860만원, 자동차 4,542만원 → 4,996만원·5,451만원으로 완화돼요.</p>
<p class="small muted">출처: {notice_link('2026000414', '인천계양지구 A6블록 공공분양')} 신청자격·당첨자 선정방법, (출산가구 소득기준 완화) 문단과 &lt;표3&gt;.</p></section>
<section class="card doc"><h2>민영주택 특별공급 기준 (2026.6.15 시행 규칙 공고)</h2>
<div class="gwrap"><table class="gtbl"><thead><tr><th>신혼부부</th><th>외벌이</th><th>맞벌이</th></tr></thead><tbody>{stages(MIN['newlywed'])}<tr><td>추첨</td><td colspan="2">소득 초과해도 부동산 3억 3,100만원 이하</td></tr></tbody></table></div>
<p>맞벌이는 부부 중 1명의 소득이 외벌이 기준(우선공급 100%, 일반공급 140%) 이하여야 해요. 생애최초·신생아는 우선공급 130%, 일반공급 160%, 그 위는 부동산 3억 3,100만원 이하면 추첨이에요.</p>
<p class="small muted">출처: {notice_link('2026000453', '광명 시티프라디움 에듀하임')} 신혼부부 특별공급 소득구분 표.</p></section>
<p class="small muted">공고마다 기준이 다를 수 있어요. 신청 전에 해당 모집공고문의 소득 기준 표를 꼭 확인하세요.</p>"""


def guide_score() -> str:
    ex = [("만 36세 미혼 무주택, 부양가족 0명, 통장 6년", dict(birth="1990-01-01", married=False, dependents=0, acctSince="2020-09-01")),
          ("만 38세 기혼(만 30세 전 혼인), 자녀 2명, 통장 12년", dict(birth="1988-05-01", married=True, marriedOn="2016-05-01", dependents=3, acctSince="2014-09-01")),
          ("만 42세 기혼, 부모님 부양 포함 4명, 통장 15년 이상 + 배우자 통장 4년", dict(birth="1984-01-01", married=True, marriedOn="2012-01-01", dependents=4, acctSince="2008-01-01", spouseAcctSince="2022-01-01"))]
    rows = "".join(f"<tr><td>{html.escape(t)}</td>{''.join(f'<td>{v}</td>' for v in score(p, '2026-09-18'))}<td><b>{sum(score(p, '2026-09-18'))}</b></td></tr>" for t, p in ex)
    nohome = "".join(f"<tr><td>{'1년 미만' if y == 0 else f'{y}년 이상'}</td><td>{2 if y == 0 else min(32, 2 + 2 * y)}</td></tr>" for y in range(0, 16))
    acct = "<tr><td>6개월 미만</td><td>1</td></tr><tr><td>6개월~1년</td><td>2</td></tr>" + "".join(f"<tr><td>{y}년 이상</td><td>{min(17, y + 2)}</td></tr>" for y in range(1, 16))
    return f"""<h1>청약 가점 계산표 (84점 만점)</h1>
<p class="muted small">「주택공급에 관한 규칙」 [별표1]의 2 나목 · 2026년 민영주택 모집공고문 가점표 원문</p>
<section class="card doc"><h2>세 항목의 합이 내 가점이에요</h2>
<ul class="doclist"><li><b>무주택기간 (32점)</b>: 만 30세가 된 날(그 전에 혼인했으면 혼인신고일)부터 계산하고, 집을 판 적이 있으면 판 날부터 다시 계산해요. 만 30세 미만 미혼이면 0점.</li>
<li><b>부양가족 (35점)</b>: 본인 제외, 공고일 현재 나 또는 배우자와 같은 등본에 있는 세대원. 0명 5점, 1명마다 5점, 6명 이상 35점.
<br><span class="small">배우자 · 직계존속은 내가 세대주이고 최근 3년 이상 계속 같은 등본에 있어야 하며, 직계존속이나 그 배우자 중 한 명이라도 집이 있으면 빼요 · 자녀는 미혼만, 만 30세 이상은 최근 1년 이상 같은 등본 · 해외 체류(90일 초과)·요양시설·외국인은 빼요.</span></li>
<li><b>청약통장 가입기간 (17점)</b>: 본인 가입기간 점수 + 배우자 통장 가입기간 50%에 해당하는 점수(최대 3점). 합계 17점까지.</li></ul></section>
<section class="card doc"><h2>무주택기간</h2><div class="gwrap"><table class="gtbl"><thead><tr><th>기간</th><th>점수</th></tr></thead><tbody><tr><td>만 30세 미만 미혼</td><td>0</td></tr>{nohome}</tbody></table></div></section>
<section class="card doc"><h2>청약통장 가입기간 (본인)</h2><div class="gwrap"><table class="gtbl"><thead><tr><th>기간</th><th>점수</th></tr></thead><tbody>{acct}</tbody></table></div>
<p>배우자 통장: 배우자 가입기간의 50%가 6개월 미만 1점, 6개월~1년 2점, 1년 이상 3점 (2024.3.25 시행).</p></section>
<section class="card doc"><h2>계산 예시 (공고일 2026.9.18 기준)</h2>
<div class="gwrap"><table class="gtbl"><thead><tr><th>예시</th><th>무주택</th><th>부양가족</th><th>통장</th><th>합계</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="small muted">예시 점수는 청약패스 판정 검증 사례와 같은 계산으로 만들었어요. 내 점수는 <a href="/">청약패스</a>에서 내 조건을 넣으면 공고마다 계산돼요.</p></section>
<p class="small muted">출처: {notice_link('2026000103', '더샵 분당하이스트')} 가점 산정기준 표·배우자 통장가입기간 점수표·부양가족의 인정 적용기준. 노부모부양 특별공급은 배우자 통장 점수를 더하지 않아요.</p>"""


def guide_deposit() -> str:
    dep = notice_pdf.notice_facts((NOTICE / "2026000453.txt").read_text(encoding="utf-8"))["deposit_rows"]
    lab = {"85": "전용 85㎡ 이하", "102": "전용 102㎡ 이하", "135": "전용 135㎡ 이하", "all": "모든 면적"}
    tr = "".join(f"<tr><td>{lab[k]}</td><td>{won(dep[k]['seoul_busan'])}</td><td>{won(dep[k]['metro'])}</td><td>{won(dep[k]['other'])}</td></tr>" for k in ("85", "102", "135", "all") if k in dep)
    return f"""<h1>청약통장 1순위 조건과 예치금 기준표</h1>
<p class="muted small">민영주택 1순위 · 2026년 모집공고문 원문 표</p>
<section class="card doc"><h2>민영주택 예치금 (만원)</h2>
<p>공고일 현재 주민등록상 사는 지역 기준이에요. 주택청약종합저축은 공고일까지 예치금을 채우면 돼요.</p>
<div class="gwrap"><table class="gtbl"><thead><tr><th>면적</th><th>서울·부산</th><th>그 밖의 광역시</th><th>그 밖의 지역</th></tr></thead><tbody>{tr}</tbody></table></div>
<p class="small muted">출처: {notice_link('2026000453', '광명 시티프라디움 에듀하임')} 청약예금 예치금액 표. 청약패스는 매일 모든 민영 공고문의 이 표를 앱 기준과 대조해요.</p></section>
<section class="card doc"><h2>1순위 가입기간</h2>
<ul class="doclist"><li><b>투기과열지구·청약과열지역</b>: 가입 24개월 경과 + 예치금 (예: 광명·성남 분당 공고 '가입기간이 24개월이 경과하고 지역별·면적별 예치금액 이상')</li>
<li><b>그 밖의 수도권</b>: 12개월 · <b>수도권 밖</b>: 6개월 (공고문에 적힌 기간이 우선)</li>
<li><b>공공분양(국민주택)</b>은 예치금 대신 납입 인정 횟수와 금액(매달 최대 25만원 인정)으로 봐요. 수도권 1순위는 보통 12개월·12회 이상.</li>
<li>규제지역 1순위는 세대주여야 하고, 2주택 이상 세대나 5년 안에 당첨된 세대는 1순위가 안 돼요.</li></ul></section>
<p class="small muted">공고마다 조건이 다를 수 있어요. 신청 전에 모집공고문의 '신청자격' 부분을 꼭 확인하세요.</p>"""


def main() -> None:
    frag = json.loads((ROOT / "tools" / "static_fragments.json").read_text(encoding="utf-8"))
    pages = {
        "story/": ("만든 이유와 데이터", "청약패스가 답하려는 질문과 쓰는 데이터(청약홈, 모집공고문, 국토부 실거래가)", frag["story"]),
        "about/": ("이용 안내", "청약패스 판정의 범위, 데이터와 검증 방식, 데이터 검증 현황, 개인정보 안내", ("" if "<h1" in frag["about"] else "<h1>이용 안내</h1>") + frag["about"]),
        "terms/": ("이용약관", "청약패스 이용약관", frag["terms"]),
        "privacy/": ("개인정보처리방침", "청약패스 개인정보처리방침", frag["privacy"]),
        "updates/": ("업데이트 내역", "청약패스 베타 업데이트 내역 — 무엇이 바뀌고 고쳐졌는지", frag["updates"]),
        "guide/income/": ("2026년 청약 소득 기준표", "특별공급·공공분양·신혼희망타운 월평균소득 기준 금액표와 단계별 기준, 출산가구 완화 — 모집공고문 원문 표", guide_income()),
        "guide/score/": ("청약 가점 계산표", "무주택기간·부양가족·청약통장 가입기간 가점표(84점)와 계산 예시 — 주택공급에 관한 규칙 별표1", guide_score()),
        "guide/deposit/": ("청약통장 1순위 조건과 예치금", "민영주택 지역·면적별 예치금 표와 1순위 가입기간 조건", guide_deposit()),
    }
    idx = "".join(f'<li><a href="/{slug}"><b>{html.escape(t)}</b></a><br><span class="small muted">{html.escape(d)}</span></li>' for slug, (t, d, _) in pages.items() if slug.startswith("guide/"))
    pages["guide/"] = ("청약 기준 가이드", "청약 소득 기준표, 가점 계산표, 예치금 기준 — 모집공고문 원문으로 만든 참고 자료",
                       f"<h1>청약 기준 가이드</h1><p>모집공고문 원문 표를 그대로 옮기고, 매일 수집하는 공고문과 대조해 확인하는 기준표예요.</p><section class=\"card doc\"><ul class=\"doclist\">{idx}</ul></section>")
    for slug, (t, d, body) in pages.items():
        out = DOCS / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(slug, t, d, body), encoding="utf-8")
    urls = [("", "daily", "1.0")] + [(s, "weekly" if s.startswith("guide") else "monthly", "0.7" if s.startswith("guide") else "0.5") for s in pages]
    sm = "".join(f"  <url><loc>{SITE}/{s}</loc><lastmod>{TODAY}</lastmod><changefreq>{c}</changefreq><priority>{p}</priority></url>\n" for s, c, p in urls)
    (DOCS / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sm}</urlset>\n', encoding="utf-8")
    print(f"[정적 문서] {len(pages)}쪽 · sitemap {len(urls)}개 주소")


if __name__ == "__main__":
    main()
