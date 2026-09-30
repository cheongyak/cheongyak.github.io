"""입주자모집공고문(PDF) 읽기.

API 에 없는 판정 정보를 공고문에서 뽑는다.
  - 신청 대상이 무주택 '세대주' 인지 '세대구성원' 인지
  - 분양가상한제 적용 여부, 실거주 의무 기간
  - 잔금일 (입주지정기간 종료일)
  - 발코니 확장비 (금액이 하나로 정해진 경우만)

청약홈 공고 페이지(PBLANC_URL)에서 PDF 링크를 찾아 내려받는다. 페이지 구조가 바뀌거나 막히면
None 을 돌려주고, 파이프라인은 기존 판정(주소·API 기반)을 그대로 쓴다. 무엇을 찾았는지는 실행 기록에 남긴다.
"""
from __future__ import annotations

import io
import re
from typing import Optional
from urllib.parse import urljoin

import httpx

UA = {"User-Agent": "Mozilla/5.0 (cheongyak-bot; +https://github.com/cheongyak/cheongyak.github.io)"}
_LINK = re.compile(r"""(?:href|src|onclick)\s*=\s*["']([^"']*?(?:\.pdf|[Aa]tchmnfl|[Dd]ownload|fileDown|FileDown)[^"']*)["']""")
_URL_IN_JS = re.compile(r"""['"]((?:https?:)?//[^'"]+?\.pdf[^'"]*)['"]|['"](/[^'"]+?\.pdf[^'"]*)['"]""")


def find_pdf_links(html: str, base: str) -> list[str]:
    out: list[str] = []
    for m in _LINK.finditer(html):
        raw = m.group(1)
        js = re.search(r"""['"]([^'"]+)['"]""", raw) if raw.lower().startswith("javascript") or "(" in raw else None
        cand = js.group(1) if js else raw
        out.append(urljoin(base, cand))
    for m in _URL_IN_JS.finditer(html):
        out.append(urljoin(base, m.group(1) or m.group(2)))
    seen, uniq = set(), []
    for u in out:
        if u not in seen and not u.startswith("javascript"):
            seen.add(u)
            uniq.append(u)
    return uniq


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages[:80])   # 공고문 일반공급 자격표가 45쪽 넘게 있는 경우가 있음 (2026-09-30 고덕 A65BL)


def fetch_notice_text(page_url: str, client: Optional[httpx.Client] = None) -> tuple[Optional[str], str, Optional[str]]:
    """(공고문 텍스트, 기록용 메시지, PDF 주소)."""
    http = client or httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=True, headers=UA)
    try:
        r = http.get(page_url)
    except Exception as e:
        return None, f"공고 페이지 접속 실패: {e.__class__.__name__}", None
    if r.status_code != 200:
        return None, f"공고 페이지 응답 {r.status_code}", None
    links = find_pdf_links(r.text, str(r.url))
    if not links:
        return None, f"PDF 링크 못 찾음 (페이지 {len(r.text)}자)", None
    last = ""
    for link in links[:4]:
        p = None
        for attempt in range(2):          # 일시적인 실패가 있어 한 번 더 시도한다
            try:
                p = http.get(link)
                if p.status_code == 200:
                    break
                last = f"응답 {p.status_code}"
            except Exception as e:
                last = e.__class__.__name__
            if attempt == 0:
                import time
                time.sleep(2)
        if p is None:
            continue
        ctype = p.headers.get("content-type", "")
        if p.status_code == 200 and (p.content[:4] == b"%PDF" or "pdf" in ctype):
            try:
                text = pdf_text(p.content)
            except Exception as e:
                return None, f"PDF 해석 실패: {e.__class__.__name__}", None
            if len(text) > 500:
                return text, f"PDF 읽음 ({len(text)}자): {link}", link
    return None, f"PDF 받기 실패({last or '형식 아님'}): " + " | ".join(links[:3]), None


def _date(y, m, d) -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def snippets(text: str, word: str, n: int = 2, width: int = 90) -> list[str]:
    """공고문에서 word 가 나오는 문장 일부 (추출 규칙을 원문 근거로 고치기 위한 진단용)."""
    t = re.sub(r"\s+", " ", text)
    out, i = [], 0
    while len(out) < n:
        i = t.find(word, i)
        if i < 0:
            break
        out.append(t[max(0, i - 20): i + width].strip())
        i += len(word)
    return out


def parse_notice(text: str) -> dict:
    """공고문 텍스트 → 판정에 쓰는 값. 확실하지 않은 항목은 넣지 않는다."""
    t = re.sub(r"[ \t]+", " ", text)
    flat = re.sub(r"\s+", "", text)
    out: dict = {}

    # 신청 대상: "…에 거주하는 무주택세대의 세대주" / "…무주택세대구성원"
    m = re.search(r"거주하는(?:만\d+세이상인)?(?:분|자)?(?:중)?(무주택세대의세대주|무주택세대주|무주택세대구성원)", flat)
    if m:
        out["need_head"] = "세대주" in m.group(1)
    elif "무주택세대주(무주택세대의세대주)를대상으로" in flat:
        out["need_head"] = True

    # 분양가상한제
    if re.search(r"분양가상한제(?:가)?미적용", flat):
        out["price_cap"] = False
    elif re.search(r"분양가상한제(?:가|를)?적용(?:되는|받는|주택)", flat):
        out["price_cap"] = True

    # 실거주 의무 (법상 수도권 분양가상한제 주택만 해당, 1~5년). 표 머리글에 섞인 '재당첨제한 10년' 등은 거른다.
    duty = None
    for m in re.finditer(r"거주의무기간(?:은|:|：)?(\d)년|(\d)년(?:간)?(?:의)?거주의무", flat):
        v = int(m.group(1) or m.group(2))
        if 1 <= v <= 5:
            duty = v
            break
    if duty is not None:
        out["residence_duty"] = duty
    elif re.search(r"거주의무(?:기간)?(?:[:：]|은|는)?없음", flat) or out.get("price_cap") is False:
        out["residence_duty"] = 0

    # 재당첨 제한 (1~10년). "재당첨제한을 적용받지 않음" 이면 0
    if re.search(r"재당첨제한(?:을|이|은)?(?:적용받지|적용되지)않", flat):
        out["rewin_years"] = 0
    else:
        # PDF 글자 순서가 뒤섞여 나오는 경우도 있다 (2026-09-29 충정로역자이르네 원문: "재당첨제한 년 적용10", "년간 재당첨 10 제한을")
        for pat in (r"재당첨제한(?:기간)?\D{0,40}?(\d{1,2})년",
                    r"재당첨제한년(?:적용)?(\d{1,2})",
                    r"년간재당첨(\d{1,2})제한"):
            m = re.search(pat, flat)
            if m and 1 <= int(m.group(1)) <= 10:
                out["rewin_years"] = int(m.group(1))
                break

    # 1순위 청약통장 가입기간 (개월): 투기과열·청약과열 24, 수도권 12, 그 밖 6 이 보통이지만 공고문 문장을 우선한다
    # 실제 문장(2026-09-30 공고문들): "1순위 : 입주자저축에 가입하여 가입기간이 24개월이 경과하고", "가입 기간이 6개월이",
    # "입주자저축에 가입한 후 12개월이 경과하고", 글자가 뒤섞인 "가입기간이 개월6 이 경과하고"
    for pat in (r"1순위[:：]?입주자저축에가입(?:하여가입기간이|한후)(\d{1,2})개월(?:이)?경과",
                r"입주자저축에가입하여가입기간이개월(\d{1,2})이경과"):
        m = re.search(pat, flat)
        if m and int(m.group(1)) in (6, 12, 24):
            out["account_months"] = int(m.group(1))
            break

    # 국민주택(공공분양) 일반공급 1순위: '1순위 입주자저축에 가입하여 1년(12개월)이 경과된 분으로서 매월 약정납입일에 월 납입금을 12회 이상 납입한 분'
    # (2026-09-30 인천계양 A6·양주회천 A-26·의정부우정 A-2·고덕 A65BL/A12BL 공고문 '일반공급 순위별 자격요건' 표)
    m = re.search(r"순위별자격요건.{0,40}?1순위-?입주자저축에가입하여(\d+)(년|개월)(?:\((\d+)개월\))?이경과된분으로서매월약정납입일에월납입금을(\d+)회이상납입", flat)
    if m:
        months = int(m.group(3)) if m.group(3) else int(m.group(1)) * (12 if m.group(2) == "년" else 1)
        out["account_months"] = months
        out["deposit_count"] = int(m.group(4))
    elif "신혼희망타운" in flat[:3000]:
        # 신혼희망타운: '입주자저축에 가입하여 6개월이 경과되고, 매월 약정납입일에 월납입금을 6회 이상 납입한 분'
        m = re.search(r"신청자격.{0,400}?입주자저축에가입하여(\d+)개월이경과되고,?매월약정납입일에월납입금을(\d+)회이상납입한분", flat)
        if m:
            out["account_months"] = int(m.group(1))
            out["deposit_count"] = int(m.group(2))

    # 잔금일: "입주지정기간 : 2026년 9월 7일~2026년 11월 30일" 또는 "입주지정기간 종료일(2026.11.30.)"
    m = re.search(r"입주지정기간[:：]?\d{4}년\d{1,2}월\d{1,2}일~(\d{4})년(\d{1,2})월(\d{1,2})일", flat) \
        or re.search(r"입주지정기간종료일\(?(\d{4})\.(\d{1,2})\.(\d{1,2})", flat)
    if m:
        out["balance"] = _date(*m.groups())

    # 발코니 확장비: 금액이 한 가지뿐일 때만 (주택형별로 다르면 건너뜀)
    amts = {int(a.replace(",", "")) for a in re.findall(r"발코니\s*확장[^\n]{0,60}?(\d{1,3}(?:,\d{3}){2,})", t)}
    if len(amts) == 1:
        won = amts.pop()
        if 1_000_000 <= won <= 200_000_000:
            out["ext"] = round(won / 100_000_000, 4)

    res = parse_residence(text)
    if res:
        out["residence"] = res
    return out


# ---- 거주 지역 요건 (기능: residence_v2) ----
# 공고문 첫머리 '해당지역 / 기타지역' 표나 LH 공고의 '지역우선 공급기준' 표를 그대로 읽는다.
# 근거: 공고문이 인용하는 「주택공급에 관한 규칙」 제4조(공급대상)·제25조·제34조(대규모 택지개발지구 우선공급).
# 실제 문장 예 (evidence/notices):
#  민영 표   "해당지역 기타지역 규제지역여부 민영 서울특별시 2년 이상 계속 거주자 (2024.08.28. 이전부터 계속 거주)
#             서울특별시 2년 미만 거주자, 경기도 및 인천광역시 거주자 투기과열지구"
#  국민 표   "주택유형 해당지역 기타경기 기타지역 규제지역여부 국민주택 (공공분양) 경기도 평택시 1년 이상 계속 거주자 (2025.09.11. 이전부터 계속 거주)
#             경기도 6개월 이상 거주자 (2026.03.11. 이전부터 계속 거주) 경기도 6개월 미만 거주자 및 전국 거주자 비규제지역"
#  LH 표     "① 해당 주택건설지역 (양주시) 30% ․ 공고일 현재 양주시 1년 이상 거주자 - 주민등록표등본상 ‘25.8.27 이전부터 …
#             ② 경기도 20% ․ 공고일 현재 경기도 6개월 이상 거주자 - 주민등록표등본상 ‘26.2.27 이전부터 … ③ 기타지역(수도권) 50% …"
#  무순위    "입주자모집공고일 현재 전국에 거주하는 무주택세대구성원", "현재 해당 주택건설지역인 경기도 광명시에 거주하는"
SIDO_NAMES = [
    ("서울특별시", "서울"), ("서울시", "서울"), ("부산광역시", "부산"), ("대구광역시", "대구"), ("인천광역시", "인천"), ("인천시", "인천"),
    ("광주광역시", "광주"), ("대전광역시", "대전"), ("울산광역시", "울산"), ("세종특별자치시", "세종"), ("경기도", "경기"),
    ("강원특별자치도", "강원"), ("강원도", "강원"), ("충청북도", "충북"), ("충청남도", "충남"), ("전북특별자치도", "전북"),
    ("전라북도", "전북"), ("전라남도", "전남"), ("경상북도", "경북"), ("경상남도", "경남"), ("제주특별자치도", "제주"),
]
CAPITAL = ["서울", "경기", "인천"]
_REG_END = r"(?:비규제지역|투기과열지구|청약과열지역|조정대상지역|규제지역)"


def _regions(text: str) -> list[str]:
    """글에 나오는 시·도 (수도권은 서울·경기·인천, '전국'은 전국)."""
    if "전국" in text:
        return ["전국"]
    out: list[str] = []
    if "수도권" in text:
        out += CAPITAL
    for long, short in SIDO_NAMES:
        if long in text and short not in out:
            out.append(short)
    return out


def _area(words: str) -> dict:
    """'경기도 성남시' → {'sido':'경기','sigungu':'성남시'}, '서울특별시' → {'sido':'서울'}, '전주시' → {'sigungu':'전주시'}."""
    w = re.sub(r"^(?:기존|입주자모집공고일현재|입주자모집공고일 현재|공고일 현재)\s*", "", words.strip())
    out: dict = {"name": w}
    for long, short in SIDO_NAMES:
        if w.startswith(long):
            out["sido"] = short
            w = w[len(long):].strip()
            break
    m = re.match(r"([가-힣]+(?:시|군))(?:\s|$)", w)
    if m:
        out["sigungu"] = m.group(1)
    return out


def _ymd(y, m, d) -> str:
    y = int(y)
    return _date(y + 2000 if y < 100 else y, m, d)


def parse_residence(text: str) -> Optional[dict]:
    """공고문의 거주 지역 요건. 못 읽으면 None (추측하지 않음).
    {'area': {'name','sido','sigungu'}, 'months': 해당지역 거주기간(0=기간 없음), 'since': 'YYYY-MM-DD'(이날 이전부터 계속 거주),
     'gyeonggi': {'months','since'} (대규모 택지의 경기도 몫), 'others': 기타지역 시·도 목록(['전국'] 가능), 'quota': {'해당':%,'경기':%,'기타':%}}"""
    t = re.sub(r"\s+", " ", text)
    # 1) 민영·국민 요약 표
    m = re.search(r"해당지역 (기타경기 )?기타지역 규제지역 ?여부 (?:민영(?:주택)?|국민주택 ?\(공공분양\)|국민주택|공공분양) (.+?) " + _REG_END, t)
    if m and len(m.group(2)) < 400:
        mid = m.group(2)
        a = re.match(r"(?:입주자모집공고일 현재 )?(?:기존 )?((?:[가-힣]+(?:특별시|광역시|특별자치시|특별자치도|도))?(?: ?[가-힣]+(?:시|군))?)", mid)
        area = _area(a.group(1)) if a and a.group(1) else None
        if not area:
            return None
        head = re.search(r"거주자\s*(?:\d\s*)?(?:\([^)]*\)|이전부터 계속 ?거주\s*\([^)]*\))?", mid)
        hpart = mid[:head.end()] if head else mid
        rest = mid[head.end():] if head else ""
        yrs = re.search(r"(\d{1,2})\s*년\s*이상|년\s*이상\s*거주자\s*(\d)", hpart)
        mos = re.search(r"(\d{1,2})\s*개월\s*이상", hpart)
        months = int(yrs.group(1) or yrs.group(2)) * 12 if yrs else (int(mos.group(1)) if mos else 0)
        sd = re.search(r"\((\d{4})\.(\d{1,2})\.(\d{1,2})\.?\s*\)?(?:\s*이전부터)?", hpart)
        out = {"area": area, "months": months, "since": _ymd(*sd.groups()) if (sd and months) else None}
        if m.group(1):   # 기타경기 칸
            g = re.search(r"경기도 (\d+)개월 이상 거주자 ?\((\d{4})\.(\d{1,2})\.(\d{1,2})", rest)
            if g:
                out["gyeonggi"] = {"months": int(g.group(1)), "since": _ymd(*g.groups()[1:])}
                rest = rest[g.end():]
        out["others"] = _regions(rest)
        return out
    # 2) LH 지역우선 공급기준 표
    m = re.search(r"① ?해당 ?주택건설지역 ?\(([^)]+)\) ?(\d{1,3}) ?% ?․? ?(.{0,200})", t)
    if m:
        area = _area(m.group(1))
        body = m.group(3).split("②")[0]
        yrs = re.match(r"공고일 현재 (?:주민등록표등본상 )?\S+ ?(?:(\d{1,2})년 이상|(\d{1,2})개월 이상)? ?거주자", body)
        months = (int(yrs.group(1)) * 12 if yrs.group(1) else int(yrs.group(2) or 0)) if yrs else 0
        sd = re.search(r"주민등록표등본상 [‘’'`](\d{2})\.(\d{1,2})\.(\d{1,2})\.? ?이전부터", body)
        out = {"area": area, "months": months, "since": _ymd(*sd.groups()) if (sd and months) else None,
               "quota": {"해당": int(m.group(2))}}
        after = t[m.start():m.start() + 1500]
        g = re.search(r"② ?경기도 ?(\d{1,3}) ?% ?․? ?공고일 현재 경기도 (\d+)개월 이상 거주자 - 주민등록표등본상 [‘’'`](\d{2})\.(\d{1,2})\.(\d{1,2})", after)
        if g:
            out["gyeonggi"] = {"months": int(g.group(2)), "since": _ymd(*g.groups()[2:])}
            out["quota"]["경기"] = int(g.group(1))
        o = re.search(r"[②③] ?기타지역(?:\([^)]*\))? ?(\d{1,3}) ?% ?․? ?공고일 현재 (.{0,140})", after)
        if o:
            out["quota"]["기타"] = int(o.group(1))
            txt = o.group(2).split("※")[0]
            out["others"] = _regions(txt)
        else:
            out["others"] = []
        return out
    # 3) 무순위·재공급·취소분: 대상자 문장 (기간 요건 없음). 지역이 여럿이면 우선순위 없이 모두 신청 가능(equal)
    #    예: "입주자모집공고일 현재 부산광역시 및 울산광역시, 경상남도에 거주하는 무주택세대구성원",
    #        "모집공고일 현재 과천시에 거주 주민등록표등본 기준 하는 무주택세대구성원", "현재 ( ) 충청북도에 거주하는 무주택"
    for m in re.finditer(r"공고일 ?현재 (?:\( ?\) )?(?:해당 주택건설지역인 )?([^.■※]{2,70}?)에 ?거주(?:하거나 ([^.■※]{2,80}?)에 ?거주)?[^.■]{0,30}?무주택", t):
        first, more = m.group(1).strip(), (m.group(2) or "")
        if "전국" in first:
            return {"area": None, "months": 0, "since": None, "others": ["전국"], "equal": True}
        regs = _regions(first + " " + more)
        single = _area(first)
        if not more and len(regs) <= 1 and (single.get("sido") or single.get("sigungu")):
            return {"area": single, "months": 0, "since": None, "others": [], "equal": True}
        if regs:
            return {"area": _area(first) if more else None, "months": 0, "since": None, "others": regs, "equal": not more}
    return None
