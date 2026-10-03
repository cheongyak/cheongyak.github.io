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


PAGE_CAP = 300   # 예전 80쪽 — 고덕 A12BL·A65BL 93쪽·두정역 83쪽 공고문 뒤쪽(최대 13쪽 2만여 자)이 빠졌다 (2026-10-02 tools/qa/pdf_audit)
ALT_TEXT: dict[str, str] = {}   # PDF 주소 → 두 번째 도구(pypdfium2)로 읽은 글 (pipeline 이 값 보완·대조에 씀)
import threading
_PDFIUM_LOCK = threading.Lock()   # pypdfium2(PDFium)는 여러 스레드에서 동시에 쓰면 프로세스가 죽는다 — 수집은 공고문을 6개 스레드로 받는다 (2026-10-02 수집 실패)


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages[:PAGE_CAP])


_ALT_SCRIPT = r"""
import sys, pypdfium2 as pdfium
data = sys.stdin.buffer.read(); cap = int(sys.argv[1]); out = []
doc = pdfium.PdfDocument(data)
for i in range(min(len(doc), cap)):
    page = doc[i]; tp = page.get_textpage()
    out.append(tp.get_text_range() or ""); tp.close(); page.close()
doc.close()
sys.stdout.buffer.write("\n".join(out).encode("utf-8"))
"""


def pdf_text_alt(data: bytes) -> Optional[str]:
    """두 번째 읽기 도구. pypdf 가 글자 순서를 뒤섞어 값을 놓치는 공고문이 있다 — 과천 푸르지오 벨라르테·라비엔오 '재당첨제한 10년'을 pypdf 로는 못 읽고
    pypdfium2 로는 읽음 (2026-10-02 pdf_audit). 설치돼 있지 않거나 실패하면 None.
    PDFium 은 C 라이브러리라 잘못되면 프로세스째 죽는다(2026-10-02 21:24 수집 exit 139 — 잠금을 걸어도 페이지 객체가 다른 스레드에서 정리되며 죽음).
    그래서 따로 띄운 파이썬 프로세스에서 읽는다 — 그쪽이 죽어도 수집은 첫 도구 값으로 계속한다"""
    import subprocess
    import sys
    try:
        import pypdfium2  # noqa: F401
    except Exception:
        return None
    with _PDFIUM_LOCK:   # 한 번에 하나씩 (메모리)
        try:
            r = subprocess.run([sys.executable, "-c", _ALT_SCRIPT, str(PAGE_CAP)], input=data, capture_output=True, timeout=90)
        except Exception:
            return None
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", "replace")


def _with_mirrors(links: list[str]) -> list[str]:
    """첨부 서버(static.applyhome.co.kr)가 새 공고 파일을 아직 못 받아 '찾을 수 없음' 글(200, 59바이트)을 돌려줄 때가 있다.
    같은 주소를 청약홈 본 서버(www.applyhome.co.kr)로 받으면 PDF 가 온다 (2026-10-03 더샵 동인센트리체·제주 아이린8차·용인 양지 서희 —
    tools/qa/pdf_fetch_probe, evidence/qa/pdf-fetch-probe.txt). 그래서 링크마다 본 서버 주소를 바로 뒤에 붙여 차례로 시도한다."""
    out: list[str] = []
    for u in links:
        out.append(u)
        if "//static.applyhome.co.kr/" in u:
            out.append(u.replace("//static.applyhome.co.kr/", "//www.applyhome.co.kr/"))
    return out


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
    for link in _with_mirrors(links[:4]):
        p = None
        for attempt in range(2):          # 일시적인 실패가 있어 한 번 더 시도한다
            try:
                p = http.get(link, headers={**UA, "Referer": str(r.url)} if attempt else UA)   # 두 번째 시도는 공고 페이지를 Referer 로 (첨부 서버가 바로 받기를 막는 경우)
                if p.status_code == 200 and (p.content[:4] == b"%PDF" or attempt):
                    break
                last = f"응답 {p.status_code}" if p.status_code != 200 else last
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
                alt = pdf_text_alt(p.content)
                if alt:
                    ALT_TEXT[link] = alt
                return text, f"PDF 읽음 ({len(text)}자{', 두 번째 도구 ' + str(len(alt)) + '자' if alt else ''}): {link}", link
            last = f"글자를 못 읽는 PDF(스캔 이미지 추정, 글자 {len(text)}자)"   # 2026-10-02: 예전엔 '형식 아님'으로만 남아 원인을 몰랐다
        elif p.status_code == 200:
            head = p.content[:8]
            kind = "HWP" if head[:4] == bytes.fromhex("d0cf11e0") else "ZIP/HWPX" if head[:2] == b"PK" else "HTML" if b"<" in head else "알 수 없음"
            snip = p.content[:120].decode("utf-8", "replace").replace("\n", " ").strip() if kind == "HTML" or len(p.content) < 400 else ""
            last = f"PDF가 아닌 파일({kind}, {ctype or '형식 표시 없음'}, {len(p.content)}바이트{(': ' + snip) if snip else ''})"
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


def _flat_pos(text: str) -> list[int]:
    """공백을 뺀 글(flat)의 i번째 글자가 원문 몇 번째 글자인지."""
    return [i for i, ch in enumerate(text) if not ch.isspace()]


def _quote_at(text: str, pos: list[int], s: int, e: int, before: int = 12, after: int = 30, cap: int = 170) -> str:
    """flat 에서 찾은 [s, e) 를 원문 문장으로 되돌린다 (값마다 '공고문 문장'으로 보여 주는 근거, 기능 notice_quotes).
    앞뒤로 조금 더 붙이고 공백을 한 칸으로. PDF 글자 순서가 뒤섞인 공고문은 원문도 뒤섞여 보인다 — 고치지 않고 그대로 둔다."""
    if not pos or s >= len(pos):
        return ""
    a, b = pos[max(0, s - before)], pos[min(len(pos), e + after) - 1] + 1
    core_a = pos[s]
    if a > 0 and not text[a - 1].isspace():          # 앞쪽 잘린 낱말은 버린다 (찾은 부분은 남김)
        sp = re.search(r"\s", text[a:core_a])
        a = a + sp.end() if sp else a
    if b < len(text) and not text[b].isspace():      # 뒤쪽 잘린 낱말도
        sp = max((m.start() for m in re.finditer(r"\s", text[pos[e - 1] + 1:b])), default=None)
        b = pos[e - 1] + 1 + sp if sp is not None else b
    q = re.sub(r"\s+", " ", text[a:b]).strip()
    q = (q[:cap] + "…") if len(q) > cap else q
    return ("…" if a > 0 else "") + q + ("…" if b < len(text) and not q.endswith("…") else "")


def parse_notice(text: str) -> dict:
    """공고문 텍스트 → 판정에 쓰는 값. 확실하지 않은 항목은 넣지 않는다."""
    t = re.sub(r"[ \t]+", " ", text)
    flat = re.sub(r"\s+", "", text)
    out: dict = {}
    pos = _flat_pos(text)
    q: dict = {}   # 값마다 근거 원문 문장 (기능 notice_quotes · 2026-10-02 미뤄둔 일 9번)
    def cite(key, m, **kw):
        if m is not None and key not in q:
            q[key] = _quote_at(text, pos, m.start(), m.end(), **kw)

    # 신청 대상: "…에 거주하는 무주택세대의 세대주" / "…무주택세대구성원"
    # 2026-10-01 감사: 2026000436 은 노부모부양 특별공급 대상자 문장('…거주하는 무주택세대주')이 먼저 걸려 일반공급에 세대주 요건이 붙었다 → 노부모부양 칸 문장은 건너뛴다
    m = next((x for x in re.finditer(r"거주하는(?:만\d+세이상인)?(?:분|자)?(?:중)?(무주택세대의세대주|무주택세대주|무주택세대구성원)", flat)
              if "노부모부양" not in flat[max(0, x.start() - 120):x.start()]), None)
    if m:
        out["need_head"] = "세대주" in m.group(1)
        cite("need_head", m, before=30)
    elif "무주택세대주(무주택세대의세대주)를대상으로" in flat:
        out["need_head"] = True
        cite("need_head", re.search(r"무주택세대주\(무주택세대의세대주\)를대상으로", flat))

    # 청약홈 공고문 첫 쪽 '단지 주요정보' 표: 머리글 '… 전매제한 거주의무기간 분양가상한제 택지유형' 다음 줄의 마지막 세 칸이 [거주의무기간] [적용|미적용] [공공택지|민간택지]
    #  2026930037 '전매제한 거주의무기간 분양가상한제 택지유형 … 현재 전매제한 도과3 없음 적용 공공택지', 2026000437 '… 10년 3년 3년 적용 공공택지(대규모 택지개발지구)'.
    #  예전에는 이 표를 못 읽어 거주의무가 '모름'으로 남았고 화면이 '실거주 의무 없음'과 '있을 수 있어요'를 함께 보였다 (2026-10-02 사용자 제보 과천 푸르지오 벨라르테)
    tbl = _summary_table(text)

    # 분양가상한제
    if (m := re.search(r"분양가상한제(?:가)?미적용", flat)):
        out["price_cap"] = False
        cite("price_cap", m)
    elif (m := re.search(r"분양가상한제(?:가|를)?적용(?:되는|받는|주택)", flat)):
        out["price_cap"] = True
        cite("price_cap", m)
    elif tbl:
        out["price_cap"] = tbl["price_cap"]
        q["price_cap"] = "(1쪽 단지 주요정보 표) " + tbl.get("quote", "")

    # 실거주 의무 (법상 수도권 분양가상한제 주택만 해당, 1~5년). 표 머리글에 섞인 '재당첨제한 10년' 등은 거른다.
    duty = tbl["residence_duty"] if tbl else None
    if tbl:
        q["residence_duty"] = "(1쪽 단지 주요정보 표) " + tbl.get("quote", "")
    if duty is None:   # LH 공고문 '구분 기준일 기간 관련 법령' 표: '거주의무 거주의무 개시일 3년 「주택법」제57조의2' · '거주의무 - 없음 「주택법」제57조의2' (2026820008·820010)
        m = re.search(r"거주의무(?:거주의무개시일|-)(없음|[1-5]년)「주택법」제57조의2", flat) or re.search(r"거주의무가([1-5]년)적용", flat)
        if m:
            duty = 0 if m.group(1) == "없음" else int(m.group(1)[0])
            cite("residence_duty", m)
    if duty is None:   # '본 아파트의 거주의무기간은 최초 입주가능일(2025.05.30.)로부터 2년간 적용됩니다' (2026910236 철산자이 더 헤리티지 — 날짜가 끼어 위 규칙이 못 읽음, 2026-10-02 사용자 제보)
        m = re.search(r"거주의무기간(?:은|는)((?:(?!전매|재당첨|거주의무).){0,40}?)([1-5])년(?:간)?(?:적용|동안|거주)", flat)
        if m:
            duty = int(m.group(2))
            cite("residence_duty", m)
    for m in ([] if duty is not None else re.finditer(r"거주의무기간(?:은|:|：)?(\d)년|(\d)년(?:간)?(?:의)?거주의무", flat)):
        v = int(m.group(1) or m.group(2))
        if 1 <= v <= 5:
            duty = v
            cite("residence_duty", m)
            break
    if duty is None and not re.search(r"거주의무|거주의무기간", flat) and re.search(r"전매제한", flat):
        out["duty_silent"] = True   # 공고문을 읽었지만 거주의무를 아예 적지 않음 (LH 2026000409·416·820011 제한사항 표에 재당첨·전매제한만). 값은 모름 그대로 — 없음으로 추측하지 않는다
    if duty is not None:
        out["residence_duty"] = duty
        # 이미 지어진 단지의 재공급·무순위는 '최초 입주가능일'이 지났을 수 있다 — 입주 기한(그날부터 3년)이 가까우면 전세를 2년 못 줄 수 있어 날짜를 둔다
        # 2026910236 '거주의무기간은 최초 입주가능일(2025.05.30.)로부터 2년간 적용' (2026-10-02)
        md = re.search(r"최초입주가능일\(?(20\d\d)\.(\d{1,2})\.(\d{1,2})\.?\)?로부터[1-5]년", flat)
        if duty and md:
            out["duty_from"] = f"{md.group(1)}-{int(md.group(2)):02d}-{int(md.group(3)):02d}"
            cite("duty_from", md, before=20)
    elif (m := re.search(r"거주의무(?:기간)?(?:[:：]|은|는)?없음", flat)) or out.get("price_cap") is False:
        out["residence_duty"] = 0
        if m:
            cite("residence_duty", m)
        elif "price_cap" in q:
            q["residence_duty"] = "(분양가상한제 미적용 → 거주의무 없음) " + q["price_cap"]
    if "residence_duty" not in out:
        q.pop("residence_duty", None)

    # 재당첨 제한 (1~10년). "재당첨제한을 적용받지 않음" 이면 0
    if (m := re.search(r"재당첨제한(?:을|이|은)?(?:적용받지|적용되지)않", flat)):
        out["rewin_years"] = 0
        cite("rewin_years", m)
    else:
        # PDF 글자 순서가 뒤섞여 나오는 경우도 있다 (2026-09-29 충정로역자이르네 원문: "재당첨제한 년 적용10", "년간 재당첨 10 제한을")
        for pat in (r"재당첨제한(?:기간)?\D{0,40}?(\d{1,2})년",
                    r"재당첨제한년(?:적용)?(\d{1,2})",
                    r"년간재당첨(\d{1,2})제한"):
            m = re.search(pat, flat)
            if m and 1 <= int(m.group(1)) <= 10:
                out["rewin_years"] = int(m.group(1))
                cite("rewin_years", m)
                break

    # 1순위 청약통장 가입기간 (개월): 투기과열·청약과열 24, 수도권 12, 그 밖 6 이 보통이지만 공고문 문장을 우선한다
    # 실제 문장(2026-09-30 공고문들): "1순위 : 입주자저축에 가입하여 가입기간이 24개월이 경과하고", "가입 기간이 6개월이",
    # "입주자저축에 가입한 후 12개월이 경과하고", 글자가 뒤섞인 "가입기간이 개월6 이 경과하고"
    for pat in (r"1순위[:：]?입주자저축에가입(?:하여가입기간이|한후)(\d{1,2})개월(?:이)?경과",
                r"입주자저축에가입하여가입기간이개월(\d{1,2})이경과"):
        m = re.search(pat, flat)
        if m and int(m.group(1)) in (6, 12, 24):
            out["account_months"] = int(m.group(1))
            cite("account_months", m, before=0)
            break

    # 국민주택(공공분양) 일반공급 1순위: '1순위 입주자저축에 가입하여 1년(12개월)이 경과된 분으로서 매월 약정납입일에 월 납입금을 12회 이상 납입한 분'
    # (2026-09-30 인천계양 A6·양주회천 A-26·의정부우정 A-2·고덕 A65BL/A12BL 공고문 '일반공급 순위별 자격요건' 표)
    m = re.search(r"순위별자격요건.{0,40}?1순위-?입주자저축에가입하여(\d+)(년|개월)(?:\((\d+)개월\))?이경과된분으로서매월약정납입일에월납입금을(\d+)회이상납입", flat)
    if m:
        months = int(m.group(3)) if m.group(3) else int(m.group(1)) * (12 if m.group(2) == "년" else 1)
        out["account_months"] = months
        out["deposit_count"] = int(m.group(4))
        q.pop("account_months", None)
        s0 = flat.find("1순위", m.start(), m.end())
        q["account_months"] = q["deposit_count"] = _quote_at(text, pos, s0, m.end(), before=0, after=10)
    elif "신혼희망타운" in flat[:3000]:
        # 신혼희망타운: '입주자저축에 가입하여 6개월이 경과되고, 매월 약정납입일에 월납입금을 6회 이상 납입한 분'
        m = re.search(r"신청자격.{0,400}?입주자저축에가입하여(\d+)개월이경과되고,?매월약정납입일에월납입금을(\d+)회이상납입한분", flat)
        if m:
            out["account_months"] = int(m.group(1))
            out["deposit_count"] = int(m.group(2))
            q.pop("account_months", None)
            s0 = flat.rfind("입주자저축에가입하여", m.start(), m.end())
            q["account_months"] = q["deposit_count"] = _quote_at(text, pos, s0, m.end(), before=0, after=10)

    # 잔금일: "입주지정기간 : 2026년 9월 7일~2026년 11월 30일" 또는 "입주지정기간 종료일(2026.11.30.)"
    m = re.search(r"입주지정기간[:：]?\d{4}년\d{1,2}월\d{1,2}일~(\d{4})년(\d{1,2})월(\d{1,2})일", flat) \
        or re.search(r"입주지정기간종료일\(?(\d{4})\.(\d{1,2})\.(\d{1,2})", flat)
    if m:
        out["balance"] = _date(*m.groups())
        cite("balance", m, before=0, after=20)

    # 발코니 확장비: 금액이 한 가지뿐일 때만 (주택형별로 다르면 건너뜀)
    amts = {int(a.replace(",", "")) for a in re.findall(r"발코니\s*확장[^\n]{0,60}?(\d{1,3}(?:,\d{3}){2,})", t)}
    if len(amts) == 1:
        won = amts.pop()
        if 1_000_000 <= won <= 200_000_000:
            out["ext"] = round(won / 100_000_000, 4)

    # 같은 값이 공고문 두 곳(1쪽 '단지 주요정보' 표와 본문 문장)에 있으면 서로 같은지 — 다르면 어느 쪽이 맞는지 사람이 봐야 한다
    # (2026-10-02 사용자 '공고문에서 은근히 잘못 가져오는 경우'. 원문 101건에서는 다른 경우 0 — 앞으로 생기면 [공고문·불일치]·데이터 확인 필요)
    conf, quotes = [], {}
    if tbl:
        quotes["거주의무·분양가상한제(1쪽 표)"] = tbl.get("quote", "")
        sd = re.search(r"거주의무기간(?:은|는)((?:(?!전매|재당첨|거주의무).){0,40}?)([1-5])년(?:간)?(?:적용|동안|거주)", flat) or re.search(r"거주의무가([1-5])년적용", flat)
        sv = int(sd.groups()[-1][0]) if sd else 0 if re.search(r"거주의무가적용되지않", flat) else None
        if sv is not None and sv != tbl["residence_duty"]:
            conf.append(f"거주의무: 1쪽 표 {tbl['residence_duty'] or '없음'}{'년' if tbl['residence_duty'] else ''} ↔ 본문 '{sd.group(0) if sd else '거주의무가 적용되지 않습니다'}'")
        if re.search(r"분양가상한제(?:가)?미적용", flat) and tbl["price_cap"]:
            conf.append("분양가상한제: 1쪽 표 '적용' ↔ 본문 '미적용'")
        tr = re.search(r"재당첨제한\s*전매제한\s*거주의무기간\s*분양가상한제\s*택지유형\s*(없음|\d{1,2}\s*년)", text)
        if tr and out.get("rewin_years") is not None:
            tv = 0 if tr.group(1) == "없음" else int(re.sub(r"\D", "", tr.group(1)))
            if tv != out["rewin_years"]:
                conf.append(f"재당첨 제한: 1쪽 표 {tr.group(1).replace(' ', '')} ↔ 본문에서 읽은 {out['rewin_years']}년")
    if conf:
        out["conflicts"] = conf
    q = {k: v for k, v in q.items() if k in out and v}
    if q:
        out["quotes"] = q

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
    st = parse_sp_table(text)
    if st:
        out["sp_table"] = st   # 재공급(무순위) 주택형에만 쓴다 — 일반분양 공고 표는 머리글이 달라 쓰지 않음 (pipeline)
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
        return _parse_rental_limits(t)
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
        # 괄호 안 날짜 앞에 설명이 붙은 공고도 있다: '(공고일로부터 1년 전, 2025.02.12. 이전부터 계속 거주)' (2026000018 제주, 2026-10-02 MASTER QA)
        sd = re.search(r"\((?:[^()\d]{0,30}\d?[^()\d]{0,10},\s*)?(\d{4})\.(\d{1,2})\.(\d{1,2})\.?\s*\)?(?:\s*이전부터)?", hpart)
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



# ---- 총자산형 일반공급 소득·총자산 (공공임대 등, 기능: rental_rules, 2026-10-02 MASTER QA QA-02·03) ----
# 부동산·자동차 따로가 아니라 '총자산(부동산+금융+기타+자동차−부채)' 기준을 쓰는 공고. 공고 종류(임대 여부)는 청약홈 RENT_SECD_NM 으로 가르고, 여기서는 원문 문장만 읽는다.
# 원문 2026000307 (군포대야미 A-1 6년 분양전환공공임대, 공고일 2026-06-30):
#  '8. 일반공급 ■ 신청자격 … ③ 무주택세대구성원 전원의 월평균소득이 … 100%[본인 및 배우자가 모두 소득이 있는 경우 200%, 가구원 수가
#   1명인 경우에는 120%, 가구원수가 2명인 경우에는 110%(본인 및 배우자가 모두 소득이 있는 경우에는 200%)]이하인 분'  → eligible (자격 상한)
#  '2단계 우선공급(1순위자) … 100%[… 140%, … 1명인 경우에는 120%, … 2명인 경우에는 110%(… 150%)] 이하인 자'      → priority (넘으면 3단계 추첨만)
#  '<표2> … 총자산보유기준 세부내역 … 합계액에서 ⑤를 차감한 금액이 362,000천원 이하', '<표3> 출산가구 총자산보유기준 완화 … 397,000천원 … 431,000천원'
# 공백 없이 맞춘다 (PDF 글에 '본 인'처럼 글자 사이 공백이 끼어 있음)
_RENT_INC = (r"(\d{2,3})%\[본인및배우자가모두소득이있는경우(\d{2,3})%,가구원수가1명인경우에는(\d{2,3})%,"
             r"가구원수가2명인경우에는(\d{2,3})%\(본인및배우자가모두소득이있는경우에는(\d{2,3})%\)\]이하")


def _inc(m) -> dict:
    return {"base": [int(m.group(1)), int(m.group(2))], "one": int(m.group(3)), "two": [int(m.group(4)), int(m.group(5))]}


def _parse_rental_limits(t: str) -> Optional[dict]:
    f = re.sub(r"\s+", "", t)
    gi = f.find("일반공급■신청자격")
    el = re.search(_RENT_INC, f[gi:gi + 2500]) if gi >= 0 else None
    pi = f.find("2단계우선공급(1순위자)-")
    pri = re.search(_RENT_INC, f[pi:pi + 1200]) if pi >= 0 else None
    rel = re.search(r"출산가구총자산보유기준완화.{0,400}?차감한금액이([\d,]+)천원이하.{0,200}?차감한금액이([\d,]+)천원이하", f)
    relax = {rel.group(1), rel.group(2)} if rel else set()
    # 표 순서가 공고마다 달라(2026000307 은 <표3> 완화표가 <표2> 앞) 완화 금액이 아닌 첫 '차감한 금액'을 기본 기준으로 본다
    base = next((m.group(1) for m in re.finditer(r"차감한금액이([\d,]+)천원이하", f) if m.group(1) not in relax), None)
    if not (el and base):
        return None
    k = lambda g: int(g.replace(",", "")) // 10   # 천원 → 만원
    out = {"kind": "total", "eligible": _inc(el), "total_asset": k(base),
           "area_max": 60 if re.search(r"전용면적60㎡이하일반공급|일반공급\(60㎡이하\)|60㎡이하만적용", f) else None}
    if pri:
        out["priority"] = _inc(pri)
    if rel:
        out["total_asset_relax"] = [k(rel.group(1)), k(rel.group(2))]
    amt = _rental_income_table(f)
    if amt:
        out["amounts"] = amt
    sp = _rental_sp_table(f)
    if sp:
        out["sp"] = sp
    return out


def _nums(s: str) -> list[int]:
    return [int(x.replace(",", "")) for x in re.findall(r"\d{1,2},\d{3},\d{3}", s)]


def _rental_income_table(f: str) -> Optional[dict]:
    """공고문 <표4> 가구원수별 금액(원)을 그대로 읽는다 — 이 공고는 1인·2인·3인 기준액이 공공분양의 '3인 이하'와 다르다
    (2026000307: 1인 120% 4,576,036 · 2인 110% 6,452,897 · 3인 100% 8,168,429). {'elig'|'pri': {'1':[외벌이, 맞벌이|None], '2':[…], '3'~'8':[…]}}"""
    one = re.search(r"\(표4-1\).{0,200}?1인일반공급도시근로자가구원수별가구당월평균소득액의\d+%([\d,]+)", f)
    i2, i3 = f.find("(표4-2)"), f.find("(표4-3)")
    if not (one and i2 >= 0 and i3 > i2):
        return None
    t2, t3 = f[i2:i3], f[i3:i3 + 4000]
    def two(label):
        m = re.search(label + r".{0,60}?의\d+%([\d,]+).{0,80}?의\d+%\(본인및배우자가모두소득이있는경우\)([\d,]+)", t2)
        return [int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))] if m else None
    def many(label):
        m = re.search(label + r".{0,60}?의\d+%((?:[\d,]{9,10}){6}).{0,80}?의\d+%\(본인및배우자가모두소득이있는경우\)((?:[\d,]{9,10}){6})", t3)
        if not m:
            return None
        a, b = _nums(m.group(1)), _nums(m.group(2))
        return (a, b) if len(a) == 6 and len(b) == 6 else None
    e2, p2 = two(r"추첨공급\(20%\)"), two(r"우선공급1순위자\(30%\)")
    e3, p3 = many(r"추첨공급\(20%\)"), many(r"우선공급\(1순위자\)\(30%\)")
    if not (e2 and p2 and e3 and p3):
        return None
    o = int(one.group(1).replace(",", ""))
    elig = {"1": [o, None], "2": e2, **{str(n): [e3[0][n - 3], e3[1][n - 3]] for n in range(3, 9)}}
    pri = {"1": [o, None], "2": p2, **{str(n): [p3[0][n - 3], p3[1][n - 3]] for n in range(3, 9)}}
    return {"elig": elig, "pri": pri}


_SUMMARY = re.compile(r"전매제한\s*거주의무기간\s*분양가상한제\s*택지유형(.{0,400}?)(없음|[1-5]\s*년)\s*(?:\([^)]{0,60}\)\s*)?(적용|미적용)\s+(공공택지|민간택지)", re.S)


def _summary_table(text: str) -> Optional[dict]:
    """'단지 주요정보' 표의 거주의무기간·분양가상한제. 값 칸이 표 모양대로 이어지지 않으면(머리글 뒤 400자 안에 없으면) 읽지 않는다"""
    m = _SUMMARY.search(text)
    if not m:
        return None
    d = m.group(2).replace(" ", "")
    return {"residence_duty": 0 if d == "없음" else int(d[0]), "price_cap": m.group(3) == "적용", "quote": re.sub(r"\s+", " ", m.group(0))[:160]}

# ---- 공공임대 특별공급 유형별 소득 기준 (기능: rental_special, 2026-10-02 MASTER QA 남은 일) ----
# 2026000307 <표4> (표4-2) 2인 · (표4-3) 3~8인: 유형 머리글('신혼부부특별공급' 등) 아래 단계마다
#  '우선공급(70%) 도시근로자 … 월평균소득액의 100% 8,168,429 … 도시근로자 … 의 120% (본인 및 배우자가 모두 소득이 있는 경우) 9,802,115 …'.
# 금액을 그대로 읽는다(공공분양 공통 표 spBase 와 1·2·3인 기준액이 다름). 단계 비율 합이 100이 아니거나 2인·3인 표의 단계가 다르면 그 유형은 읽지 않는다.
# 결과 {유형: {'tiers': [[단계, 비율, 3인+ 외벌이 %, 맞벌이 %]], 'pct2': [[2인 외벌이 %, 맞벌이 %]], 'amt': {'2'~'8': [[외벌이 원, 맞벌이 원] 단계별]}}}
RENT_SP = {"다자녀가구특별공급": "multichild", "노부모부양특별공급": "elder", "생애최초특별공급": "first", "신혼부부특별공급": "newlywed", "신생아특별공급": "newborn"}
_RENT_TIER = (r"(우선공급|일반공급|추첨공급)\((\d{1,2})%\)도시근로자가구원수별가구당월평균소득액의(\d{2,3})%((?:\d{1,2},\d{3},\d{3})+)"
              r"도시근로자가구원수별가구당월평균소득액의(\d{2,3})%\(본인및배우자가모두소득이있는경우\)((?:\d{1,2},\d{3},\d{3})+)")


def _rental_sp_blocks(seg: str) -> dict:
    pos = sorted((m.start(), m.end(), RENT_SP[m.group(0)]) for m in re.finditer("|".join(RENT_SP), seg))
    out = {}
    for i, (_, e, k) in enumerate(pos):
        body = seg[e: pos[i + 1][0] if i + 1 < len(pos) else len(seg)]
        out[k] = [(m.group(1), int(m.group(2)), int(m.group(3)), _nums(m.group(4)), int(m.group(5)), _nums(m.group(6))) for m in re.finditer(_RENT_TIER, body)]
    return out


def _rental_sp_table(f: str) -> Optional[dict]:
    i2, i3 = f.find("(표4-2)"), f.find("(표4-3)")
    i5 = f.find("<표5>", i3) if i3 >= 0 else -1
    if not (0 <= i2 < i3 < i5):
        return None
    b2, b3 = _rental_sp_blocks(f[i2:i3]), _rental_sp_blocks(f[i3:i5])
    out = {}
    for k, t3 in b3.items():
        if not t3 or any(len(x[3]) != 6 or len(x[5]) != 6 for x in t3) or sum(x[1] for x in t3) != 100:
            continue
        t2 = b2.get(k) or []
        if t2 and ([x[:2] for x in t2] != [x[:2] for x in t3] or any(len(x[3]) != 1 or len(x[5]) != 1 for x in t2)):
            continue   # 2인 표와 3인 이상 표의 단계가 다르면 읽지 않는다 (추측 금지)
        row = {"tiers": [[x[0], x[1], x[2], x[4]] for x in t3],
               "amt": {str(n): [[x[3][n - 3], x[5][n - 3]] for x in t3] for n in range(3, 9)}}
        if t2:
            row["pct2"] = [[x[2], x[4]] for x in t2]
            row["amt"]["2"] = [[x[3][0], x[5][0]] for x in t2]
        out[k] = row
    return out or None


# ---- 재공급 공고 주택형별 특별공급 세대수 (기능: resupply_special, 2026-10-02 블라인드 감사에서 '확인 필요'만 나오던 문제) ----
# 청약홈은 무순위·재공급 주택형에 특별공급 세대수를 주지 않는다. 공고문 공급대상 표를 읽는다:
#  2026930036 '… 총공급 세대수 특별공급 세대수 주거 전용면적 … 소계 노부모부양 신혼부부 계 2026930036 01 084.7450D 84D 84.7450 25.5789 110.3239 53.6674 163.9913 55.1901 2 1 1 2'
#  2026930031 '… 일반공급 세대수 … 생애최초 계 … 01 059.9979A 59A 59.9979 21.3074 81.3053 42.2340 123.5393 30.5725 1 1 1 -'
#  행 = 면적 6개(전용·공용·소계·기타공용·계약·대지지분) → 총공급 → 머리글 순서의 유형별 세대 → 계 → (일반공급)
SP_NAMES = {"다자녀가구": "multichild", "다자녀": "multichild", "신혼부부": "newlywed", "노부모부양": "elder", "생애최초": "first", "신생아": "newborn", "기관추천": "agency"}


def parse_sp_table(text: str) -> Optional[dict]:
    t = re.sub(r"\s+", " ", text)
    h = re.search(r"특별공급 세대수(.{0,200}?)(20\d{8}) 01 ", t)
    if not h:
        return None
    heads = [SP_NAMES[w] for w in re.findall("|".join(sorted(SP_NAMES, key=len, reverse=True)), h.group(1))]
    if not heads or len(set(heads)) != len(heads):
        return None
    out = {}
    for m in re.finditer(r"\b0\d (\d{2,3}\.\d{4}[A-Z]{0,2}) \S+ ((?:(?!0\d \d{2,3}\.\d{4})[\d.,]+ |- ){7,14})", t[h.start():h.start() + 3000]):
        nums = m.group(2).split()
        vals = nums[6:]
        if len(vals) < len(heads) + 2:
            continue
        cnt = lambda v: 0 if v == "-" else int(v) if v.isdigit() else None
        total, per, sp_sum = cnt(vals[0]), [cnt(v) for v in vals[1:1 + len(heads)]], cnt(vals[1 + len(heads)])
        if None in per or sp_sum is None or sum(per) != sp_sum or total is None or sp_sum > total:
            continue   # 표 숫자가 맞지 않으면 읽지 않는다 (추측 금지)
        row = dict(zip(heads, per))
        row["total"] = sp_sum
        out[m.group(1)] = row
    return out or None


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


# ---- 단지 규모 (기능: complex_size, 2026-10-02 청약봇 V2 STEP 0-2) ----
# 모집공고문 '공급규모' 문장에서 단지 총세대수·동 수를 읽는다. 예: '아파트 지하 2층, 지상 22층 6개동 총 426세대 중 일반분양 426세대'(2026000453),
# 공공 '공공분양주택 19∼20층 6개동 전용면적 60㎡ 이하 463세대'(2026000409), 신혼희망타운 '시흥하중 A-4블록 신혼희망타운 총 584세대 중 … 11개동'(2026820011).
# PDF 글자 순서가 흐트러져 숫자만 뒤에 모인 공고문('지하 층 지상 층 개동 총 세대 중 : 3 , 30~38 , 7 1,191', 2026910243)은 읽지 않는다(확인 불가) — 추측하지 않는다.
def parse_complex(text: str) -> Optional[dict]:
    if not text:
        return None
    t = re.sub(r"\s+", " ", text)
    for m in re.finditer(r"공급\s?규모", t):
        w = t[m.end():m.end() + 260]
        if re.search(r"지하\s*층\s*지상\s*층", w) or re.search(r"개동\s*총\s*세대", w):
            continue   # 숫자가 문장 밖으로 빠진 공고문
        hh = re.search(r"총\s*([\d,]{2,6})\s*세대", w) or re.search(r"블록\s*([\d,]{2,6})\s*세대", w) \
            or re.search(r"\d\s*개\s*동[^세]{0,40}?([\d,]{2,6})\s*세대", w)
        bd = re.search(r"(\d{1,3})\s*개\s*동", w)
        if not hh:
            continue
        h = int(hh.group(1).replace(",", ""))
        b = int(bd.group(1)) if bd else None
        if not (10 <= h <= 20000) or (b is not None and not (1 <= b <= 100 and b <= h)):
            continue
        return {"households": h, "buildings": b, "quote": w[:120].strip()}
    return None


def single_status(c: Optional[dict]) -> str:
    """나홀로 아파트 3상태: 'no'(동 2개 이상 확인) · 'maybe'(동 1개 확인, 또는 동 수를 모르고 총 100세대 미만) · 'unknown'(판단 근거 없음).
    동 1개라도 주상복합 대단지처럼 사정이 다를 수 있어 '가능성 있음'으로만 둔다."""
    if not c:
        return "unknown"
    b, h = c.get("buildings"), c.get("households")
    if b is not None:
        return "no" if b >= 2 else "maybe"
    if h is not None and h < 100:
        return "maybe"
    return "unknown"


# ---- 두 읽기 도구 결과 합치기 (2026-10-02 사용자 '공고문에서 은근히 잘못 가져오는 경우' · tools/qa/pdf_audit) ----
MERGE_SCALAR = ("need_head", "price_cap", "residence_duty", "rewin_years", "account_months", "deposit_count", "balance")
MERGE_STRUCT = ("residence", "mc_quota", "schedule", "pub_limits", "score_ratio", "sp_table", "duty_from")


def merge_alt(found: dict, alt: dict) -> list[str]:
    """pypdf 로 읽은 값(found)에 두 번째 도구 값(alt)을 더한다. 한쪽만 읽힌 값은 채우고, 둘 다 읽혔는데 다르면 found 값을 두고 conflicts 에 남긴다
    (어느 쪽이 맞는지 사람이 원문을 봐야 함 → 데이터 확인 필요). 반환: 기록할 문장"""
    notes = []
    for k in MERGE_SCALAR:
        a, b = found.get(k), alt.get(k)
        if a is None and b is not None:
            found[k] = b
            if (alt.get("quotes") or {}).get(k):   # 두 번째 도구로 읽은 값은 그 도구가 본 문장을 근거로
                found.setdefault("quotes", {})[k] = alt["quotes"][k]
            notes.append(f"{k}={b!r} (첫 도구는 못 읽음)")
            if k == "residence_duty":
                found.pop("duty_silent", None)
        elif a is not None and b is not None and a != b:
            found.setdefault("conflicts", []).append(f"읽기 도구에 따라 {k} 값이 달라요: {a!r} ↔ {b!r}")
    for k in MERGE_STRUCT:
        if not found.get(k) and alt.get(k):
            found[k] = alt[k]
            notes.append(f"{k} (첫 도구는 못 읽음)")
    return notes
