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
    # 2026-10-01 감사: 2026000436 은 노부모부양 특별공급 대상자 문장('…거주하는 무주택세대주')이 먼저 걸려 일반공급에 세대주 요건이 붙었다 → 노부모부양 칸 문장은 건너뛴다
    m = next((x for x in re.finditer(r"거주하는(?:만\d+세이상인)?(?:분|자)?(?:중)?(무주택세대의세대주|무주택세대주|무주택세대구성원)", flat)
              if "노부모부양" not in flat[max(0, x.start() - 120):x.start()]), None)
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
    mc = parse_mc_quota(text)
    if mc:
        out["mc_quota"] = mc
    sc = parse_schedule(text)
    if sc:
        out["schedule"] = sc
    pl = parse_pub_limits(text)
    if pl:
        out["pub_limits"] = pl
    sr = parse_score_ratio(text)
    if sr:
        out["score_ratio"] = sr
    return out


# ---- 민영 1순위 가점제·추첨제 비율 (기능: region_first_score, 2026-10-01) ----
# 공고문 '전용면적별 1순위 가점제/추첨제 적용비율' 표: '전용면적 60㎡ 이하 40% 60%', '전용면적 60㎡ 초과 85㎡ 이하 70% 30%',
#   '전용면적 85㎡ 초과 - 100%' (2026000453·403·103·454 원문). 2026000454 는 칸에 주택형 '84A / 84B' 가 끼어 있다.
# 표가 있는 것 같은데 못 읽으면 {'unknown': True}, 흔적이 없으면 None (추측하지 않음). 가점제+추첨제가 100% 가 아니면 못 읽은 것으로 본다.
def parse_score_ratio(text: str) -> Optional[dict]:
    t = re.sub(r"\s+", " ", text)
    m = re.search(r"전용면적별 1순위 가점제\s?[/·]\s?추첨제 적용\s?비율 ?구분 ?가점제 ?추첨제", t)
    if not m:
        return {"unknown": True} if re.search(r"가점제 ?[/·]? ?추첨제 ?적용 ?비율", t) else None
    rows = []
    for r in re.finditer(r"전용면적 (?:(\d{2,3})\s?㎡ ?초과 ?~? ?)?(?:(\d{2,3})\s?㎡ ?이하)? ?(?:\d{2,3}[A-Z]{0,2} ?/? ?)*?(-|\d{1,3}) ?%? ?(-|\d{1,3}) ?%",
                         t[m.end():m.end() + 260]):
        lo, hi = r.group(1), r.group(2)
        if not lo and not hi:
            continue
        a = 0 if r.group(3) == "-" else int(r.group(3))
        b = 0 if r.group(4) == "-" else int(r.group(4))
        if a + b != 100:
            return {"unknown": True}
        rows.append({"over": int(lo) if lo else 0, "upto": int(hi) if hi else None, "score": a, "lottery": b})
    return {"rows": rows} if rows else {"unknown": True}


# ---- 공공분양 일반공급 소득·자산 기준 (기능: pub_general_limits) ----
# LH 공공분양 공고문(2026000409·414·416)에서 읽는다.
#   신청자격 요약표 소득 줄의 일반공급 칸: '(세대) 월평균소득 100% 이하 (맞벌이 200%) * 전용면적 60㎡ 이하만 적용' → 자격 상한
#   2단계 우선공급 문장: '일반공급 신청자격에 해당되며 … 1순위자로서 무주택세대구성원 전원의 월평균소득이 … 100%(본인 및 배우자가
#     모두 소득이 있는 경우 140%) 이하인 자' → 우선공급 상한 (넘으면 3단계 추첨공급만)
#   자산: '부동산(건물+토지) 215,500천원 이하', '자동차 45,420천원 이하'
#   적용 면적: '전용면적 60㎡ 이하만 적용'·'60㎡ 이하 일반공급' 문구가 있으면 60㎡ 이하, 없으면 이 공고 일반공급 전체(2026000409 는 59㎡뿐)
# 요약표 일반공급 소득 칸이나 자산 금액을 찾지 못하면 None (화면은 60㎡ 이하 공공분양을 '확인 필요'로 둔다)
def parse_pub_limits(text: str) -> Optional[dict]:
    t = re.sub(r"\s+", " ", text)
    if "신혼희망타운" in t[:3000]:
        return _parse_town_limits(t)
    cap = re.search(r"월평균소득 (\d{2,3})% 이하 \(맞\s*벌\s*이\**\s*(\d{2,3})%\)(\s*\*\s*전용면적 60㎡ 이하만 적용)?\s*자산", t)
    pri = re.search(r"일반공급 신청자격에 해당되며[^.]{0,80}1순위자로서 무주택세대구성원 전원의 월평균소득이[^.]{0,80}?"
                    r"(\d{2,3})%\s*\(본인 및 배우자가 모두 소득이 있는 경우 (\d{2,3})%\) 이하인 자", t)
    re_ = re.search(r"부동산\s*\(건물\s*\+\s*토지\)\s*([\d,]+)천원 이하", t)
    car = re.search(r"자동차\s*([\d,]+)천원 이하", t)
    if not (cap and re_ and car):
        return None
    out = {"cap": [int(cap.group(1)), int(cap.group(2))],
           "real_estate": int(re_.group(1).replace(",", "")) // 10,   # 천원 → 만원
           "car": int(car.group(1).replace(",", "")) // 10}
    if pri:
        out["priority"] = [int(pri.group(1)), int(pri.group(2))]
    le60 = cap.group(3) or re.search(r"전용면적 60㎡ 이하 일반공급|일반공급\s*\(60㎡ 이하\)", t)
    out["area_max"] = 60 if le60 else None
    return out


# ---- 공급유형별 접수 일정 (기능: notice_schedule) ----
# LH 공공분양 공고문의 '• 신청시간 : (사전청약 당첨자) … , (특별공급) … , (일반공급) …' 문장을 읽는다.
# 청약홈 API 가 특별공급 접수일을 주지 않는 LH 공고(2026000409·414·416)에서 특별공급 날짜를 채우는 데 쓴다.
_SCH_LABEL = {"사전청약 당첨자": "pre", "특별공급": "special", "일반공급": "general"}
_SCH_DATE = re.compile(r"(?<![\d.])(?:(20\d\d)\.\s*)?(\d{1,2})\.\s*(\d{1,2})\.?(?!\d)")


def parse_schedule(text: str) -> Optional[dict]:
    m = re.search(r"신청시간\s*:\s*(\([^\n]*(?:\n[ \t]+\([^\n]*)*)", text)
    if not m:
        return None
    line = re.sub(r"\s+", " ", m.group(1))
    parts = re.split(r"\((사전청약 당첨자|특별공급|일반공급)\)", line)
    out = {}
    for label, seg in zip(parts[1::2], parts[2::2]):
        seg = re.sub(r"\d{1,2}:\d{2}", " ", seg)      # 10:00 같은 시각은 빼고 날짜만
        ds, year = [], None
        for y, mo, d in _SCH_DATE.findall(seg):
            year = int(y) if y else year
            if year is None or not (1 <= int(mo) <= 12 and 1 <= int(d) <= 31):
                continue
            ds.append(_date(year, mo, d))
        if ds:
            out[_SCH_LABEL[label]] = [ds[0], ds[-1]]
    return out if "special" in out else None


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


# ---- 다자녀 특별공급 지역별 배정 (기능: mc_quota) ----
# 실제 문장 (evidence/notices):
#  민영 2026000399 "다자녀가구 특별공급 해당시도(서울특별시) 거주자 (50%) … 기타지역(경기도 및 인천광역시) 거주자 (50%)"
#  LH 2026000409 "다자녀 특별공급 지역 우선공급 기준 … ① 경기도 50% ․ 공고일 현재 주민등록표등본상 해당 주택건설지역(의정부시) 거주자에게 우선 공급
#                 단, 남는 물량은 경기도 거주자에게 공급 ② 기타지역(수도권) 50% ․ 공고일 현재 주민등록표등본상 수도권(서울특별시, 인천광역시)에 거주하는 분"
#  LH 2026000416 "① 경기도 50% ․ 공고일 현재 해당 주택건설지역(양주시) 1년 이상 거주자에게 우선 공급. 단, 남는 물량은 경기도 6개월 이상 거주자에게 공급
#                 - 주민등록표등본상 ‘25.8.27 이전부터 … ② 기타지역(수도권) 50% ․ … 경기도(6개월 미만 거주자 포함), 서울특별시, 인천광역시에 거주하는 분"
#  LH 2026000414 "다자녀 특별공급 및 일반공급 지역 우선공급 기준 … ① 해당 주택건설지역 (인천광역시) 50% … ② 기타지역(수도권) 50% … 서울특별시, 경기도에 거주하는 분"
def _regions_listed(text: str) -> list[str]:
    """'수도권(서울특별시, 인천광역시)' 처럼 괄호로 나열했으면 나열한 것만, 아니면 _regions."""
    m = re.search(r"수도권\(([^)]+)\)", text)
    return _regions(m.group(1)) if m else _regions(text)


SHORT_SIDO = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]


def _regions_any(text: str) -> list[str]:
    """정식 이름이 없으면 '서울, 인천' 같은 짧은 이름도 읽는다."""
    r = _regions(text)
    if r:
        return r
    return [x for x in SHORT_SIDO if re.search(r"(?:^|[\s,(·및])" + x + r"(?:$|[\s,)·및])", text)]


def parse_mc_quota(text: str) -> Optional[dict]:
    """다자녀 특별공급 지역별 배정. {'buckets': [{'name','pct','regions'(시·도), 'first'(그 안의 해당지역 우선), 'rest_months'}]}.
    배정 표가 있는 것 같은데 못 읽으면 {'unknown': True}, 흔적이 없으면 None (추측하지 않음)."""
    t = re.sub(r"\s+", " ", text)
    # 민영 공급세대수 표: '다자녀가구 특별공급 해당시·도(광명시 및 경기도) 거주자(50%) … 기타지역(서울특별시 및 인천광역시) 거주자(50%)'
    #  (2026000399 '해당시도(서울특별시) 거주자 (50%)', 2026000394 '여주시 및 경기도 거주자(50%) … 서울특별시 및 인천광역시 거주자(50%)',
    #   2026000431 '해당 시,도(남양주시, 경기도) … 기타지역(서울, 인천)', 2026000449 표 사이에 다른 글이 끼어 있음)
    m = re.search(r"다자녀가구 특별공급 (?:해당\s?시\s?[,·]?\s?도\s?\(([^)]+)\)|([가-힣]+ 및 [가-힣]+)) ?거주자 ?\((\d{1,3})%\)", t)
    if m:
        first = m.group(1) or m.group(2)
        m2 = re.search(r"(?:기타지역\s?\(([^)]+)\)|([가-힣]+ 및 [가-힣]+)) ?거주자 ?\((\d{1,3})%\)", t[m.end():m.end() + 900])
        if m2:
            return {"buckets": [{"name": "해당 시·도", "pct": int(m.group(3)), "regions": _regions_any(first)},
                                {"name": "기타지역", "pct": int(m2.group(3)), "regions": _regions_any(m2.group(1) or m2.group(2))}]}
        return {"unknown": True}
    m = re.search(r"다자녀(?:가구)? 특별공급 (?:및 일반공급 )?지역 우선공급 기준", t)
    if m:
        w = t[m.end():m.end() + 1500]
        out = []
        for b in re.finditer(r"[①②③] ?(경기도|해당 ?주택건설지역 ?\(([^)]+)\)|기타지역(?:\(([^)]+)\))?) ?(\d{1,3}) ?% ?[․ㆍ·]? ?(.*?)(?=[①②③]|※|$)", w):
            name, body, pct = b.group(1), b.group(5), int(b.group(4))
            if name == "경기도":
                f = re.search(r"해당 주택건설지역\(([^)]+)\) ?(?:(\d)년 이상 (?:계속 )?)?거주자에게 우선 공급", body)
                sd = re.search(r"주민등록표등본상 [‘’'`](\d{2})\.(\d{1,2})\.(\d{1,2})\.? ?이전부터", body)
                r = re.search(r"남(?:는|은) 물량은 경기도 (?:(\d+)개월 이상 (?:계속 )?)?거주자", body)
                bk = {"name": "경기도", "pct": pct, "regions": ["경기"]}
                if f:
                    bk["first"] = {"area": _area(f.group(1)), "months": int(f.group(2)) * 12 if f.group(2) else 0,
                                   "since": _ymd(*sd.groups()) if (sd and f.group(2)) else None}
                if r:
                    bk["rest_months"] = int(r.group(1)) if r.group(1) else 0
                out.append(bk)
            elif b.group(2):
                a = _area(b.group(2))
                out.append({"name": "해당 주택건설지역", "pct": pct, **({"regions": [a["sido"]]} if a.get("sido") else {"area": a, "regions": []})})
            else:
                out.append({"name": "기타지역" + (f"({b.group(3)})" if b.group(3) else ""), "pct": pct,
                            "regions": ["전국"] if (b.group(3) == "전국" or "전국" in body) else _regions_listed(body)})
        return {"buckets": out} if len(out) >= 2 else {"unknown": True}
    if re.search(r"다자녀[^.]{0,60}(?:\d{1,3}\s?%\s?[․ㆍ·]|거주자\s?\(\d{1,3}%\))", t):
        return {"unknown": True}
    return None


# ---- 신혼희망타운 소득·총자산 기준 (기능: town_rules) ----
# LH 신혼희망타운 공고문(2026820008·009·011)의 소득 표 '우선·일반공급 … 130% … 140% (본인 및 배우자가 모두 소득이 있는 경우)'와
# <표3> 총자산보유기준 '①+②+③+④ 합계액에서 ⑤를 차감한 금액이 362,000천원(362백만원) 이하', <표4> 출산가구 완화(397,000·431,000천원)를 읽는다.
# 총자산 = 부동산 + 금융자산 + 기타자산(임차보증금 등) + 자동차 − 부채 (공고문 <표3>)
def _parse_town_limits(t: str) -> Optional[dict]:
    inc = re.search(r"우선·일반공급 전년도 도시근로자 가구당 월평균소득의 (\d{2,3})% [\d, ]+ 전년도 도시근로자 가구당 월평균소득의 (\d{2,3})% "
                    r"\(본인 및 배우자가 모두 소득이 있는 경우\)", t)
    amts = []
    for m in re.finditer(r"합계액에서 ⑤를 차감한 금액이 ([\d,]+)\s*(천원|백만원) 이하", t):
        v = int(m.group(1).replace(",", ""))
        v = v // 10 if m.group(2) == "천원" else v * 100   # → 만원
        if v not in amts:
            amts.append(v)
    if not (inc and amts):
        return None
    out = {"kind": "town", "cap": [int(inc.group(1)), int(inc.group(2))], "total_asset": amts[0]}
    # 신청자격 ③ '무주택세대구성원 전원의 월평균소득이 … 130%(단, 본인 및 배우자가 모두 소득이 있는 경우에는 200%) 이하' (2026820008~011).
    # cap(130/140%)은 1·2단계 우선공급 기준이고, 자격 상한은 이 값이다 (2026-10-01 감사에서 발견: 예전에는 140%를 자격 상한으로 씀)
    el = re.search(r"월평균소득이[^.]{0,60}?(\d{2,3})%\s*\(단,?\s*본인 및 배우자가 모두 소득이 있는 경우(?:에는)?\s*(\d{2,3})%\)\s*이하", t)
    if el:
        out["eligible"] = [int(el.group(1)), int(el.group(2))]
    if len(amts) >= 3:
        out["total_asset_relax"] = amts[1:3]
    return out



# ---- 공고문 대조용 사실 (기능: notice_crosscheck) ----
# 화면에 쓰는 수치가 이 공고문 원문과 같은지 매 수집마다 대조하려고, 원문에서 숫자 표를 그대로 뽑아 둔다 (판정에는 쓰지 않는다).
#  - income_rows: '도시근로자 가구당 월평균소득(액)의 N% a b c d e f' (3인 이하 ~ 8인, 원)
#  - deposit_rows: 민영 청약예금 예치금 표 '전용면적 85㎡ 이하 300만원 250만원 200만원' 등 (만원)
#  - asset_thousand: '부동산 … ○○○천원 이하', '자동차 … ○○○천원 이하' 숫자 (천원)
#  - price_seen: 주택형별 청약홈 분양가(최고가)가 원문 숫자로 나오는지 (천원·만원·원 표기)
def notice_facts(text: str, prices_man: Optional[dict] = None) -> dict:
    t = re.sub(r"[ \t]+", " ", text)
    flat = re.sub(r"\s+", "", text)
    rows = {}
    for m in re.finditer(r"도시근로자 가구당 월평균소득(?:액)?의 (\d{2,3})%\s*(?:\([^)]{0,40}\))?\s*((?:[\d,]{7,11}\s+){5}[\d,]{7,11})", t):
        nums = [int(x.replace(",", "")) for x in m.group(2).split()]
        if all(1_000_000 <= v <= 60_000_000 for v in nums):
            rows.setdefault(m.group(1), nums)
    for m in re.finditer(r"(\d{2,3})% 이하\s*((?:~[\d,]{7,11}원\s*){6})", t):   # 민영 표기 '130% 이하 ~9,793,892원 …'
        nums = [int(x.replace(",", "")) for x in re.findall(r"~([\d,]+)원", m.group(2))]
        if len(nums) == 6 and all(1_000_000 <= v <= 60_000_000 for v in nums):
            rows.setdefault(m.group(1), nums)
    dep = {}
    for m in re.finditer(r"(전용면적\s?(85|102|135)\s?㎡\s?이하|모든\s?면적)\s+([\d,]+)만원\s+([\d,]+)만원\s+([\d,]+)만원", t):
        k = m.group(2) or "all"
        if k in dep:
            continue
        # 표 머리글의 지역 순서를 읽는다 (공고마다 '그 밖의 광역시'가 앞에 오기도 한다)
        head = t[max(0, m.start() - 400):m.start()]
        hl = head[head.rfind("구"):] if "구" in head else head
        pos = {"seoul_busan": hl.rfind("특별시 및 부산"), "metro": max(hl.rfind("그 밖의 광역시"), hl.rfind("그밖의 광역시")), "other": hl.rfind("광역시를 제외")}
        vals = [int(m.group(i).replace(",", "")) for i in (3, 4, 5)]
        if all(v >= 0 for v in pos.values()):
            keys = sorted(pos, key=pos.get)
            dep[k] = {keys[i]: vals[i] for i in range(3)}
        else:
            dep[k] = {"seoul_busan": vals[0], "metro": vals[1], "other": vals[2], "order_guess": True}
    assets = {"부동산": sorted({int(x.replace(",", "")) for x in re.findall(r"부동산[^\n]{0,40}?([\d]{2,3},\d{3})천원\s?이하", t)}),
              "자동차": sorted({int(x.replace(",", "")) for x in re.findall(r"자동차[^\n]{0,40}?([\d]{2},\d{3})천원\s?이하", t)}),
              "부동산_만원": sorted({int(a) * 10000 + int(b.replace(",", "")) for a, b in re.findall(r"부동산가액\s?(\d)억\s?([\d,]{1,5})만원\s?이하", t)})}
    seen = {}
    for ty, man in (prices_man or {}).items():
        if man:
            seen[ty] = any(f"{v:,}" in flat for v in (man * 10, man, man * 10000))
    return {"income_rows": rows, "deposit_rows": dep, "asset_thousand": assets, "price_seen": seen}
