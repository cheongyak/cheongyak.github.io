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
    return "\n".join((p.extract_text() or "") for p in reader.pages[:40])


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
    return out
