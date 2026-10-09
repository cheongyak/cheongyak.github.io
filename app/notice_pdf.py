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


_PLUMBER_SCRIPT = r"""
import sys, io, json, pdfplumber
data = sys.stdin.buffer.read(); cap = int(sys.argv[1]); out = []; tables = []
with pdfplumber.open(io.BytesIO(data)) as pdf:
    for i, page in enumerate(pdf.pages[:cap]):
        out.append(page.extract_text(x_tolerance=1.5, y_tolerance=3) or "")
        try:
            for tb in page.extract_tables():
                tables.append({"page": i + 1, "rows": [[(c or "").replace("\n", " ").strip() for c in row] for row in tb]})
        except Exception:
            pass
        page.flush_cache()
sys.stdout.buffer.write(json.dumps({"text": "\n".join(out), "tables": tables}, ensure_ascii=False).encode("utf-8"))
"""


def pdf_text_plumber(data: bytes, cap: int = 150) -> Optional[dict]:
    """세 번째 읽기 도구 pdfplumber (LH 임대, 기능 lh_pdf_multi, 2026-10-05 사용자 '임대/청년주택도 pdf 를 잘못 읽는 경우가 많으니 여러 방법으로 보완').
    글자 사이 간격으로 낱말을 나눠(x_tolerance 1.5) pypdf 처럼 표 숫자가 붙어 나오는 일('1,259,7882,099,646')이 적고, 표를 칸 단위로도 뽑는다.
    → {"text": 글, "tables": [{"page", "rows"}]}. pypdfium2 와 같은 이유로 따로 띄운 프로세스에서 읽는다. 설치돼 있지 않거나 실패하면 None."""
    import json as _json
    import subprocess
    import sys
    try:
        import pdfplumber  # noqa: F401
    except Exception:
        return None
    with _PDFIUM_LOCK:
        try:
            r = subprocess.run([sys.executable, "-c", _PLUMBER_SCRIPT, str(cap)], input=data, capture_output=True, timeout=240)
        except Exception:
            return None
    if r.returncode != 0:
        return None
    try:
        return _json.loads(r.stdout.decode("utf-8", "replace"))
    except Exception:
        return None


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


_AMT = r"\d{1,3}(?:,\d{3})+"
_PAY_HEAD = re.compile(r"계약금\(?(?:계약시|계약 시)?(\d{1,2})%\)?(?:와|과|,)?((?:(?:\d차|\d회)?중도금[가-힣()]{0,14}?\(?\d{1,2}%\)?(?:와|과|,)?)*)잔금(?:\((?:입주시)?(\d{1,3})%\)|(\d{1,3})%)?")
_SUPPLY_WORD = re.compile(r"공급금액|분양가격?|분양금액|공급가격?|주택가격|분양대금|총분양금액|아파트공급|공급가")


def _row_check(seg: str, c: int, unit: int, mi: int = None) -> tuple[int, list[int], set]:
    """표 머리 뒤 글(seg)의 금액 줄에서 계약금% 가 맞는 줄 수, 그리고 '1차 정액 + 2차 나머지'로 나뉜 줄의 1차 금액들.
    금액 셋이 이어진 곳 (T, a, b): a = T × c% 면 한 번에 내는 줄, a + b = T × c% 이고 a < T × c% 면 나뉜 줄. T 는 집값 크기(5천만 원 이상)만."""
    whole, fixed, Ts = 0, [], set()
    for r in re.finditer(r"(?<![\d,])(?=(" + _AMT + r")\s+(" + _AMT + r")\s+(" + _AMT + r"))", seg):   # 금액이 줄마다 따로 있어도(2026910033)
        T_, a_, b_ = (int(x.replace(",", "")) * unit for x in r.groups())
        want = T_ * c / 100
        if T_ < 50_000_000 or b_ >= T_:   # 낼 돈 다음 칸은 집값보다 작다 — 건축비·부가세(10%)·합계 줄을 계약금 10% 로 보지 않게
            continue
        tol = max(10_000, unit)   # 공고문은 계약금을 만 원 아래 절사·천 원 단위로 적기도 함(2026930037 952,180,000 × 20% = 190,436,000 → 190,430,000)
        if abs(a_ - want) <= tol:
            # 계약금 다음 금액도 비율과 맞아야 한다: 중도금이 없는 표면 잔금(T × (100 − c)%), 있는 표면 중도금 한 회차(T × 중도금% 이하)
            # (2026000436 본 표 10/60/30 의 줄이 옆 '발코니확장금액 계약금(10%) 잔금(90%)' 머리를 맞는 것처럼 보이게 했다)
            # 중도금 없는 표의 잔금 칸은 융자금(주택도시기금)이 따로 빠지기도 해(2026820007 잔금 − 융자금 ≈ 73%) '집값의 절반 이상'으로 본다
            if mi is not None and (b_ < T_ * 0.5 if mi == 0 else b_ > T_ * mi / 100 + tol):
                continue
            whole += 1; Ts.add(T_)
        elif 0 < a_ < want * 0.9 and abs(a_ + b_ - want) <= tol:
            fixed.append(a_); Ts.add(T_)
    return whole, fixed, Ts


def pay_terms(text: str) -> tuple[dict | None, dict | None]:
    """분양대금 표에서 (비율, 계약금 나눔). 비율 = {contract, mid, balance, quote, rows}. 못 믿으면 (None, None).
    - 머리 형식: '계약금(5%) 중도금(60%) 잔금(35%)' · '계약금10% 1차중도금15% … 잔금'(LH, 중도금 여러 차례 합) · '계약금(계약시10%) 잔금(입주시90%)' ·
      '계약금10%와 잔금90%' · '중도금이자후불제대출(60%)'. 잔금 % 가 없으면 100 − 계약금 − 중도금
    - 머리 앞 60자에 공급금액·분양가격·주택가격 등 분양대금 낱말이 있고, 설치위치·제조사·품목(옵션 표)·'사전청약당첨자 대상'(다른 당첨자 표)이 아니어야 함
    - 그 표의 금액 줄(머리 뒤 3,000자 안, 다음 머리 전까지)에서 계약금% 가 맞는 줄이 1개 이상이어야 받음(표 줄 대조)
    - 받은 표들의 비율이 둘 이상이면(주택형마다 다름 등) 읽지 않음"""
    flat = re.sub(r"\s+", "", text)
    pos = _flat_pos(text)
    heads = [m for m in _PAY_HEAD.finditer(flat)]
    ok_ratios, first, fixed_all, whole_all, found = {}, None, [], 0, []
    for k, m in enumerate(heads):
        c = int(m.group(1))
        mids = [int(x) for x in re.findall(r"(\d{1,2})%", m.group(2) or "")]
        mi = sum(mids)
        b = int(m.group(3) or m.group(4)) if (m.group(3) or m.group(4)) else 100 - c - mi
        if not (c + mi + b == 100 and 0 < c <= 30):
            continue
        pre = flat[max(0, m.start() - 150): m.start()]
        if not _SUPPLY_WORD.search(pre) and not re.search(r"분양대금은$", pre) and "분양대금" not in pre:
            continue
        # 옵션·확장 표는 집값 크기(5천만 원 이상) 금액 줄이 없어 아래 표 줄 대조에서 걸러진다 — 여기서는 설치위치·제조사(가전·가구 표)·사전청약 당첨자 전용 표만 뺀다.
        # 제목 낱말(발코니확장·옵션)로는 거르지 않는다: 본 표 제목 '공급금액(발코니확장금액 별도)'(2026000437)·열 '발코니확장비용'(2026000041)도 그 낱말을 쓴다
        if re.search(r"설치위치|제조사", pre[-70:]) or re.search(r"사전청약당첨자대상", pre[-80:]) and not re.search(r"사전청약당첨자외", pre):
            continue
        # 그 표의 금액 줄: 원문(t)에서 머리 위치부터 다음 머리 전까지(최대 3,000자)
        s0 = pos[m.start()] if m.start() < len(pos) else len(text)   # pos 는 공백 뺀 글 → 원문(text) 위치
        nxt = pos[heads[k + 1].start()] if k + 1 < len(heads) and heads[k + 1].start() < len(pos) else len(text)
        seg = re.sub(r"[ \t]+", " ", text[s0: min(nxt, s0 + 4000)])
        u0 = flat.rfind("단위", max(0, m.start() - 1500), m.start())   # 표 위 가장 가까운 '(단위: 세대, 천원)' · '[단위:천원]' · '(단위:세대,만원)'(2026000103)
        uw = flat[u0: u0 + 16] if u0 >= 0 else ""
        unit = 10000 if "만원" in uw or re.search(r"\(만원\)", pre[-150:]) else 1000 if "천원" in uw or re.search(r"\(천원\)", pre[-150:]) else 1   # 열 머리 '주택가격(천원)'(2026000041)
        whole, fixed, Ts = _row_check(seg, c, unit, mi)
        if whole + len(fixed) == 0 and unit == 1 and re.search(r"주택가격", pre[-60:]):
            # 단위 표시가 멀리 있는 LH 표(2026820009 신혼희망타운 '주택형 타입 층별 타입별 주택가격 계약금10% 중도금20% 잔금')는 천원 단위 —
            # 본 표 열 이름 '주택가격'이 바로 앞에 있고, 금액이 모두 천원 단위 집값 크기(5만~200만)이며 3줄 이상 맞을 때만 (원 단위 옵션 표를 천 배로 읽지 않게)
            w2, f2, T2 = _row_check(seg, c, 1000, mi)
            if w2 + len(f2) >= 3 and all(50_000_000 <= x <= 2_000_000_000 for x in T2):
                whole, fixed, Ts = w2, f2, T2
        if whole + len(fixed) == 0:
            continue   # 표 줄 금액이 이 비율과 맞지 않음 → 이 머리는 믿지 않는다
        found.append((m, (c, mi, 100 - c - mi), whole, fixed, Ts, bool(re.search(r"옵션|품목|확장", pre[-40:]))))
    # 다른 비율의 머리가 확인한 금액 줄이 모두 더 큰 표의 줄이면(그 표 옆에 붙은 옵션 표 머리 — 2026000436 '발코니확장금액 계약금(10%) 잔금(90%)') 그 머리는 뺀다.
    # 같은 크기로 겹치면(사전청약 당첨자 표와 일반 표가 같은 집값 줄 — 2026000409) 어느 쪽인지 몰라 읽지 않는다
    # 또 제목(머리 앞 40자)이 옵션·품목·확장이고 금액이 다른 표의 가장 싼 집값의 절반도 안 되면 옵션 합계 표(2026930034 플러스옵션 합계 55,210,000).
    # 제목 없이 금액만 작다고 빼면 안 된다 — 2026000419 는 84~128㎡(7~8.7억) 계약금 5%, 펜트하우스(29~31억) 10% 로 주택형마다 달라 읽지 않는 게 맞다
    keep = [h for h in found if not any(g[1] != h[1] and ((h[4] <= g[4] and len(g[4]) > len(h[4])) or (h[5] and max(h[4]) < 0.5 * min(g[4]))) for g in found)]
    for m, key, whole, fixed, Ts, _opt in keep:
        ok_ratios[key] = ok_ratios.get(key, 0) + whole + len(fixed)
        if first is None:
            first = (m, key)
        if key == first[1]:
            fixed_all += fixed; whole_all += whole
    if len(ok_ratios) == 2 and re.search(r"사전청약당첨자대상", flat) and re.search(r"사전청약당첨자외", flat):
        # 사전청약 당첨자 표와 그 밖의 당첨자 표가 붙어 있어(2026000409) 제목만으로 짝을 모를 때: 공고문에 '사전청약당첨자 외 당첨자 대상'이라고 적힌 표(추가선택품목 납부 안내 등)의
        # 납부 일정(계약금·중도금 %)과 같은 비율의 본 표를 그 밖의 당첨자 표로 본다 — 새로 청약하는 사람은 '그 밖의 당첨자'
        gen = set()
        for g in heads:
            pre_g = flat[max(0, g.start() - 120): g.start()]
            if re.search(r"사전청약당첨자외", pre_g[-90:]):
                gen.add((int(g.group(1)), sum(int(x) for x in re.findall(r"(\d{1,2})%", g.group(2) or ""))))
        pick = [k for k in ok_ratios if (k[0], k[1]) in gen]
        if len(pick) == 1:
            ok_ratios = {pick[0]: ok_ratios[pick[0]]}
            first = next((h[0], h[1]) for h in keep if h[1] == pick[0])
            fixed_all = [x for h in keep if h[1] == pick[0] for x in h[3]]
            whole_all = sum(h[2] for h in keep if h[1] == pick[0])
    if len(ok_ratios) != 1:
        return None, None
    m, (c, mi, b) = first
    ratio = {"contract": c / 100, "mid": mi / 100, "balance": b / 100, "rows": ok_ratios[(c, mi, b)],
             "quote": _quote_at(text, pos, m.start(), m.end(), before=10, after=20)}
    split = None
    # 겹쳐 찾으면 건축비·부가세(10%) 짝이 '나뉘지 않은 계약금 10%'처럼 보일 수 있어(2026000403) 나뉜 줄이 2배 이상 많고 1차 금액이 모두 같을 때만
    if fixed_all and len(set(fixed_all)) == 1 and len(fixed_all) >= 2 * whole_all:
        days = re.search(r"(\d{1,3})(일|개월)이?내", flat[m.end(): m.end() + 400])   # '30일 이내' · '1개월 이내' · '1개월내'
        split = {"first_won": fixed_all[0], "rest_within": days.group(1) + days.group(2) if days else None, "rows": len(fixed_all)}
    return ratio, split


_SP_WORD = r"(?:특별공급|생애최초|신혼부부|다자녀|신생아|노부모부양|기관추천|이전기관)"


def _in_special_section(flat: str, pos: int, back: int = 250) -> bool:
    """pos 가 특별공급 칸(대상자 문장) 안인가 — 앞 back 글자에서 특별공급 낱말이 '일반공급'보다 나중에 나오면 특별공급 칸으로 본다."""
    w = flat[max(0, pos - back):pos]
    sp = max((m.end() for m in re.finditer(_SP_WORD, w)), default=-1)
    gen = max((m.end() for m in re.finditer(r"일반공급", w)), default=-1)
    return sp > gen


def need_head_general(flat: str):
    """일반공급 신청 대상이 세대주로 한정되는지 (공급 전체 기준. 규제지역 '1순위만 세대주'는 화면의 규제지역 규칙이 따로 본다).
    1) '일반공급은 … 무주택세대주(…)를 대상으로' / 일반공급 칸 '대상자 ■ … 거주하는 무주택세대주' (재공급·무순위)
    2) 민영 '신청자격' 표의 '세대주 요건' 줄: 머리 칸(특별공급 유형들 + 1순위 + 2순위) 수와 칸 값 수가 같을 때만 2순위 칸으로
    둘 다 없으면 None. 돌려주는 값: (True/False, 근거 위치 매치)"""
    m = re.search(r"일반공급은[^■。]{0,40}?(무주택세대의세대주|무주택세대주|무주택세대구성원)", flat) \
        or re.search(r"일반공급(?:\([^)]{0,30}\))?구분내용대상자■?(?:금회)?입주자모집공고일현재[^■]{0,80}?거주하는(?:만\d+세이상인)?(?:분|자)?(무주택세대의세대주|무주택세대주|무주택세대구성원)", flat)
    if m:
        return "세대주" in m.group(1), m
    t = re.search(r"신청자격(?:특별공급)?일반공급((?:기관추천|다자녀가구|신혼부부|노부모부양자?|생애최초|신생아|청년)*)(?:1순위2순위|순위1순위2)", flat)
    if t:
        n = len(re.findall(r"기관추천|다자녀가구|신혼부부|노부모부양|생애최초|신생아|청년", t.group(1))) + 2
        c = re.compile(r"세대주요건((?:-|필요|불필요){%d})(?!-|필요|불필요)" % n).search(flat, t.end(), t.end() + 400)
        if c:
            cells = re.findall(r"불필요|필요|-", c.group(1))
            if len(cells) == n:
                return cells[-1] == "필요", c
    # 3) LH 공공분양 '일반공급 신청자 ■ 공급신청자격자 • 주택공급신청은 무주택세대구성원 중 1인만 가능 … ※ 단, 노부모부양 특별공급을 신청하는 경우 세대주만'
    m = re.search(r"일반공급신청자[^■]{0,60}■공급신청자격자[:：]?(?:성년자인무주택세대구성원)?•?주택공급신청은무주택세대구성원중1인만가능", flat)
    if m:
        return False, m
    return None


def _price_cap_self(flat: str, x) -> bool:
    """'분양가상한제 적용주택' 문구가 이 주택 이야기인가 (2026-10-09 블라인드 대조: 2026000402 공공임대가 '분양가상한제 적용주택 등에 이미 당첨되어…'·
    '재당첨제한 적용주택(이전기관 종사자 특별공급 주택, 분양가상한제 적용주택, …)' 같은 법 설명 문장으로 '적용'이 됐다).
    이 주택: '…분양가상한제 적용주택으로/입니다', 당첨 시 재당첨 표 '당첨된 주택의 구분 … 분양가상한제 적용주택(제1항제3호)'.
    법 설명: 뒤가 '등'·','·'의'(분양가 공개·총금액), 앞이 '…주택(' 목록"""
    after, before = flat[x.end():x.end() + 3], flat[max(0, x.start() - 60):x.start()]
    if re.match(r"등|,|의|\)", after) or re.search(r"(?:대상주택|적용주택)\($", before[-12:]) or "재당첨제한대상주택(" in before[-30:]:
        return False
    return bool(re.match(r"으로|입니다|이며|이므로", after)) or "당첨된주택의구분적용기간" in before


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
    # 2026-10-09 원문 대조(블라인드 판독 60건): 첫 '거주하는 무주택…' 문장이 대개 특별공급(다자녀·생애최초) 대상자 칸이라, 재공급 2026930031·034 는
    # '일반공급은 … 무주택세대주를 대상으로'인데 특별공급 문장(무주택세대구성원)을 읽어 세대원에게 일반공급 '가능'이 나왔다 → 일반공급 문장·신청자격 표를 먼저 본다
    nh = need_head_general(flat)
    m = None if nh else next((x for x in re.finditer(r"거주하는(?:만\d+세이상인)?(?:분|자)?(?:중)?(무주택세대의세대주|무주택세대주|무주택세대구성원)", flat)
                              if "노부모부양" not in flat[max(0, x.start() - 120):x.start()] and not _in_special_section(flat, x.start())), None)
    if nh:
        out["need_head"] = nh[0]
        cite("need_head", nh[1], before=30)
    elif m:
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
    elif (m := next((x for x in re.finditer(r"분양가상한제(?:가|를)?적용(?:되는|받는|주택)", flat) if _price_cap_self(flat, x)), None)):
        out["price_cap"] = True
        cite("price_cap", m)
    elif tbl:
        out["price_cap"] = tbl["price_cap"]
        q["price_cap"] = "(1쪽 단지 주요정보 표) " + tbl.get("quote", "")

    # 실거주 의무 (법상 수도권 분양가상한제 주택만 해당, 1~5년). 표 머리글에 섞인 '재당첨제한 10년' 등은 거른다.
    mu = bool(tbl and tbl.get("mu"))   # 무순위 1쪽 표(택지유형 칸 없음)는 본문 문장이 없을 때만 거주의무로 쓴다 — 본문 문장이 더 자세함(2026910236 '최초 입주가능일로부터 2년')
    duty = tbl["residence_duty"] if tbl and not mu else None
    if tbl and not mu:
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
    if duty is None and mu:
        duty = tbl["residence_duty"]
        q["residence_duty"] = "(1쪽 단지 주요정보 표) " + tbl.get("quote", "")
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

    # 전매제한 (기능 resale_limit, 2026-10-05 사용자 '6 진행') — 본문 문장을 먼저, 없으면 1쪽 '단지 주요정보' 표 칸
    rs = parse_resale(flat)
    if rs:
        out["resale"] = {k: v for k, v in rs.items() if k not in ("m",)}
        cite("resale", rs["m"])
        rc = resale_cell(flat)   # 1쪽 표와 본문이 다르면 사람이 봐야 한다 (conflicts)
        if rc is not None and rs.get("months") is not None and not rs.get("until_reg") and not rs.get("passed") and rc != rs["months"]:
            out.setdefault("_conf_resale", f"전매제한: 1쪽 표 {rc}개월 ↔ 본문 {rs['months']}개월")

    yt = parse_youth(flat)   # 청년 특별공급 소득·자산 기준 (기능 youth_special)
    if yt:
        out["youth"] = yt

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

    # 계약금·중도금·잔금 비율 (기능 contract_from_notice, 2026-10-07 제보 '계약금 10% 고정' · 10-08 '제대로 읽도록 개선 + 재발 방지').
    # 원칙: 표 머리 글자만 믿지 않는다 — 머리 바로 뒤 그 표의 금액 줄에서 '계약금 = 공급금액 × 계약금%'(또는 1차+2차 합)가 실제로 맞는 줄이 있어야 받는다.
    # (머리만 보고 읽었더니 2026000437·438 발코니 확장 표의 '중도금(10%)', 2026000020 가구 옵션 표의 '중도금(80%)'를 분양대금으로 잘못 읽은 일이 있었다)
    pr, split = pay_terms(text)
    if pr:
        out["pay_ratio"] = {k: pr[k] for k in ("contract", "mid", "balance")}
        q["pay_ratio"] = pr["quote"]
        if split:
            out["contract_split"] = split

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
    if out.get("_conf_resale"):
        conf.append(out.pop("_conf_resale"))
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
    if not pl and (m := re.search(r"국민주택\((?:5|10|6)년공공건설임대\)", flat)) and (m2 := re.search(r"소득또는자산기준-{5}(?!-)", flat)):
        # 민간 5·10년 공공건설임대(국민주택): 신청자격 표의 '소득 또는 자산기준' 칸이 모두 '-' — 소득·자산 기준이 없다 (기능 rent_noincome,
        # 2025000645 이천 카사펠리스 '국민주택(5년 공공건설임대) … 신청자격 … 소득 또는 자산기준 - - - - -'). 표가 다르면 읽지 않는다(판정 범위 밖 그대로)
        pl = {"kind": "none"}
        cite("pub_limits", m2, before=200)
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
    """민영 '전용면적별 1순위 가점제/추첨제 적용비율' 표 → {'rows': [{'over','upto','score','lottery'}]}, 표 문구는 있는데 못 읽으면 {'unknown': True}, 표가 없으면 None.
    2026-10-03 보강 (사용자 제보 화면 '가점제·추첨제 비율 표를 읽지 못했어요'):
      ① 주택형을 쉼표로 나열한 줄 '전용면적 60㎡ 초과 85㎡ 이하 71, 84A, 84B 40% 60%' (2026000463 향남역 그로브 스위첸)
      ② 첫 도구가 글자 순서를 뒤섞은 표 '적용비율 - 1 / 구분 가점제 추첨제 전용면적 초과 이하60 85㎡ ㎡ 40% 60%' (2026000498·0444·0436) —
         줄은 '전용면적'으로 나뉘어 각 줄의 면적·비율이 그 줄 안에 있다. 줄마다 초과·이하와 면적 수가 맞고 합 100%, 줄끼리 면적이 빈틈없이 이어질 때만 읽는다
      ③ 낱말 사이 공백 '추 첨제'·'전용 면적'·'초 과' (2026000354)"""
    t = re.sub(r"\s+", " ", text)
    for a_, b_ in ((r"추 ?첨 ?제", "추첨제"), (r"전용 ?면적", "전용면적"), (r"초 ?과", "초과"), (r"이 ?하", "이하")):   # '추 첨제'·'전용 면적'·'초 과' (2026000354)
        t = re.sub(a_, b_, t)
    m = re.search(r"전용면적별 1?\s?순위 가점제\s?[/·]?\s?추첨제 적용\s?비율(?: ?- ?1 ?/)? ?구분 ?가점제 ?추첨제", t)
    if not m:
        return {"unknown": True} if re.search(r"가점제 ?[/·]? ?추첨제 ?적용 ?비율", t) else None
    seg = re.split(r"가점 ?산정 ?기준|■|※", t[m.end():m.end() + 320])[0]
    pieces = list(re.finditer(r"전용면적(.*?)(?<![\dA-Za-z])(-|\d{1,3}) ?%? ?(-|\d{1,3}) ?%", seg))
    rows = []
    for r in pieces:
        body = r.group(1)
        sizes = [int(x) for x in re.findall(r"(\d{2,3})\s?㎡", body)] + [int(x) for x in re.findall(r"(?:초과|이하)(\d{2,3})(?![\dA-Za-z])", body)]
        sizes = sorted(set(sizes))
        over_w, upto_w = "초과" in body, "이하" in body
        if over_w and upto_w and len(sizes) == 2:
            lo, hi = sizes
        elif upto_w and not over_w and len(sizes) == 1:
            lo, hi = 0, sizes[0]
        elif over_w and not upto_w and len(sizes) == 1:
            lo, hi = sizes[0], None
        else:
            return {"unknown": True}
        a = 0 if r.group(2) == "-" else int(r.group(2))
        b = 0 if r.group(3) == "-" else int(r.group(3))
        if a + b != 100:
            return {"unknown": True}
        rows.append({"over": lo, "upto": hi, "score": a, "lottery": b})
    # 줄끼리 면적이 빈틈없이 이어져야 한다 (예: 60 이하 → 60 초과 85 이하 → 85 초과). 아니면 뒤섞인 글을 잘못 짝지은 것일 수 있어 unknown
    for x, y in zip(rows, rows[1:]):
        if x["upto"] is None or y["over"] != x["upto"]:
            return {"unknown": True}
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
        pt = _parse_pub_table(t, re_, car)
        if pt:
            return pt
        return _parse_rental_limits(t)
    out = {"cap": [int(cap.group(1)), int(cap.group(2))],
           "real_estate": int(re_.group(1).replace(",", "")) // 10,   # 천원 → 만원
           "car": int(car.group(1).replace(",", "")) // 10}
    if pri:
        out["priority"] = [int(pri.group(1)), int(pri.group(2))]
    le60 = cap.group(3) or re.search(r"전용면적 60㎡ 이하 일반공급|일반공급\s*\(60㎡ 이하\)", t)
    out["area_max"] = 60 if le60 else None
    return out


def _parse_pub_table(t: str, re_, car) -> Optional[dict]:
    """공공분양식 기준을 쓰는 분양전환공공임대 (기능 rental_pub_table, 2026-10-09 익산 부송에코르 10년 공공임대 2026000402).
    신청자격 요약표 대신 '(표3) 전년도 도시근로자 가구원수별 가구당 월평균소득 기준' 표에 일반공급 단계별 가구원수 금액이 있고(1~8인),
    자산은 '부동산(건물+토지) 215,500천원 이하 · 자동차 45,420천원 이하'(총자산형이 아님).
      우선공급 (1순위자) (30%) … 100% 1인~8인 … 140% (본인 및 배우자가 모두 소득이 있는 경우) 2인~8인  → priority
      추첨공급 (20%) … 100% 1인~8인 … 200% (본인 및 배우자가 모두 소득이 있는 경우) 2인~8인            → eligible (신청 가능 상한)
    금액이 도시근로자 2025 × % (1인 +20%p, 2인 외벌이 +10%p — 공고문 문장)와 1원 단위로 같을 때만 받는다(아니면 None — 화면은 판정하지 않음)."""
    from app.lh_terms import URBAN_2025 as U
    if not (re_ and car):
        return None
    i = t.find("(표3) 전년도 도시근로자 가구원수별 가구당 월평균소득 기준")
    if i < 0:
        return None
    seg = t[i: i + 2500]
    seg = seg[: seg.find("다자녀")] if "다자녀" in seg else seg
    N8, N7 = r"((?:[\d,]{9,10} ){8})", r"((?:[\d,]{9,10} ){7})"
    def tier(label):
        m = re.search(label + r" \(\d{1,2}%\) 도시근로자 가구원수별 가구당 월평균소득액의 (\d{2,3})% " + N8 +
                      r"도시근로자 가구원수별 가구당 월평균소득액의 (\d{2,3})% \(본인 및 배우자가 모두 소득이 있는 경우\) " + N7, seg + " ")
        if not m:
            return None
        one = [int(x.replace(",", "")) for x in m.group(2).split()]
        two = [int(x.replace(",", "")) for x in m.group(4).split()]
        return int(m.group(1)), one, int(m.group(3)), two
    pri, elig = tier(r"우선공급 \(1순위자\)"), tier(r"추첨공급")
    if not elig:
        return None
    def check(tr, dual2):
        pct, one, dpct, two = tr
        want1 = [round(U[n] * (pct + (20 if n == 1 else 10 if n == 2 else 0)) / 100) for n in range(1, 9)]
        want2 = [round(U[n] * (dual2 if n == 2 else dpct) / 100) for n in range(2, 9)]
        return all(abs(a - b) <= 1 for a, b in zip(one, want1)) and all(abs(a - b) <= 1 for a, b in zip(two, want2))
    if not check(elig, elig[2]):
        return None
    # 2인 맞벌이 우선공급은 150% (공고문 '가구원 수가 2명인 경우에는 110%(본인 및 배우자가 모두 소득이 있는 경우에는 150%)')
    if pri and not check(pri, 150):
        pri = None
    amt = lambda tr: {str(n): [tr[1][n - 1], (tr[3][n - 2] if n >= 2 else None)] for n in range(1, 9)}
    out = {"kind": "pub_table", "eligible": {"base": [elig[0], elig[2]], "one": elig[0] + 20, "two": [elig[0] + 10, elig[2]]},
           "amounts": {"elig": amt(elig)}, "real_estate": int(re_.group(1).replace(",", "")) // 10, "car": int(car.group(1).replace(",", "")) // 10,
           "area_max": 60 if re.search(r"전용면적 60㎡ 이하 일반공급|일반공급\s*\(60㎡ 이하\)|60㎡ 이하만 적용", t) else None}
    if pri:
        out["priority"] = {"base": [pri[0], pri[2]], "one": pri[0] + 20, "two": [pri[0] + 10, 150]}
        out["amounts"]["pri"] = amt(pri)
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
    # 표 머리 변형 (2026-10-03 원문 대조 evidence/qa/notices): '규제 지역 여부'(2026000185 거제) · '국민'(2026000081 광주) · '국민주택 (5년공공건설임대)'(2025000645 이천)
    m = re.search(r"해당지역 (기타경기 )?기타지역 규제 ?지역 ?여부 (?:민영(?:주택)?|국민주택 ?\([^)]{1,20}\)|국민주택|공공분양|국민) (.+?) " + _REG_END, t)
    if m and len(m.group(2)) < 400:
        mid = m.group(2)
        a = re.match(r"(?:입주자모집공고일 현재 )?(?:기존 )?((?:[가-힣]+(?:특별시|광역시|특별자치시|특별자치도|도))?(?: ?[가-힣]+(?:시|군))?)", mid)
        area = _area(a.group(1)) if a and a.group(1) else None
        if not area:
            return None
        head = re.search(r"거주자\s*(?:\d\s*)?(?:\([^)]*\)|이전부터 계속 ?거주\s*(?:\d\s*)?\([^)]*\))?", mid)   # '거주자 이전부터 계속 거주1 (2025.10.08. )' 숫자가 뒤로 밀림 (2026000471, 10-09 블라인드 대조)
        hpart = mid[:head.end()] if head else mid
        rest = mid[head.end():] if head else ""
        yrs = re.search(r"(\d{1,2})\s*년\s*이상|년\s*이상\s*(?:계속\s*)?거주자\s*(\d)|년\s*이상\s*(?:계속\s*)?거주자\s*이전부터 계속 ?거주\s*(\d)", hpart)   # '년 이상 계속 거주자1': 숫자가 뒤로 밀린 글 (2026000444 제주 아이린8차, 2026-10-03 사용자 제보)
        mos = re.search(r"(\d{1,2})\s*개월\s*이상", hpart)
        if not yrs and not mos and re.search(r"년\s*이상|개월\s*이상", hpart):
            return None   # 거주기간 요건 낱말은 있는데 숫자를 못 찾음 → '요건 없음(0)'으로 두지 않고 못 읽음 (화면 '확인 필요')
        months = int(yrs.group(1) or yrs.group(2) or yrs.group(3)) * 12 if yrs else (int(mos.group(1)) if mos else 0)
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
    # 2-2) SH 공고의 <표2> 지역우선 공급기준 (2026000041 마곡지구 17단지 토지임대부, 2026-10-03 원문 대조)
    #   "지역우선 공급기준 기준일 우선공급비율 지역구분 해당지역(서울) 기타지역(수도권) … 입주자모집공고일 (2026.02.27.) 100% 0%
    #    ● 입주자모집공고일 현재 서울특별시 2년 이상 계속 거주자 ● 입주자모집공고일 현재 서울특별시 2년 미만 거주자 ● 입주자모집공고일 현재 경기도, 인천광역시 거주자 ※"
    m = re.search(r"지역우선 공급기준 기준일 .{0,120}?해당지역\([^)]+\) 기타지역\([^)]+\).{0,120}?\((\d{4})\.(\d{1,2})\.(\d{1,2})\.?\) (\d{1,3}) ?% (\d{1,3}) ?%"
                  r" ● 입주자모집공고일 현재 ([가-힣]+(?: [가-힣]+(?:시|군))?) (\d{1,2})년 이상 (?:계속 )?거주자 (.{0,200})", t)
    if m:
        y, mo, d = (int(x) for x in m.groups()[:3])
        n = int(m.group(7))
        rest = m.group(8).split("※")[0]
        return {"area": _area(m.group(6)), "months": n * 12, "since": _date(y - n, mo, d),
                "quota": {"해당": int(m.group(4)), "기타": int(m.group(5))}, "others": _regions(rest)}
    # 3) 무순위·재공급·취소분: 대상자 문장 (기간 요건 없음). 지역이 여럿이면 우선순위 없이 모두 신청 가능(equal)
    #    예: "입주자모집공고일 현재 부산광역시 및 울산광역시, 경상남도에 거주하는 무주택세대구성원",
    #        "모집공고일 현재 과천시에 거주 주민등록표등본 기준 하는 무주택세대구성원", "현재 ( ) 충청북도에 거주하는 무주택"
    #        "입주자모집공고일 (2026.10.08.) 현재 익산시 또는 전북특별자치도에 거주(주민등록표등본 기준)하는 성년자(만19세 이상)인 무주택" (2026000402 — 공고일 뒤 날짜 괄호, 'A 또는 B' = A 우선·B 도 가능)
    for m in re.finditer(r"공고일 ?(?:\( ?\d{4}\.\d{1,2}\.\d{1,2}\.? ?\) ?)?현재 (?:\( ?\) )?(?:해당 주택건설지역인 )?([^.■※]{2,70}?)에 ?거주(?:하거나 ([^.■※]{2,80}?)에 ?거주)?[^.■]{0,40}?무주택", t):
        first, more = m.group(1).strip(), (m.group(2) or "")
        if not more and (o := re.fullmatch(r"([가-힣]+(?:시|군)) 또는 ([가-힣]+(?:특별자치도|도|광역시|특별시|특별자치시))", first)):
            first, more = o.group(1), o.group(2)
        if "전국" in first or first == "국내":   # '공고일 현재 국내에 거주하는 무주택세대구성원' (2025910266 청계 노르웨이숲 무순위)
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


# ---- 전매제한 (기능 resale_limit) ----
# 민영 표준 문장 '■ 본 주택의 전매제한은 최초 당첨자발표일로부터 적용되며 기간은 아래와 같습니다. 구분 특별공급 일반공급 전매제한기간 [당첨자발표일(2026.09.22.)로부터] 6개월|1년|3년|없음|소유권이전등기시까지|
#   소유권이전등기일까지(다만, 그 기간이 3년을 초과하는 경우 3년)' (2026000103·202·314·386·403·422·443·444·022),
# LH 제한사항 표 '전매제한 (최초)당첨자발표일 3년' (2026000409·820008·820009), LH 문장 '입주자로 선정된 날(2026.10.08)로부터 3년간 전매가 금지',
# 재공급·무순위 '전매제한은 최초 입주자모집공고의 당첨자발표일(2023.01.04.)로부터 3년간 (단, 3년 내 소유권이전등기 시 해제) 적용(되어 현재 전매제한 기간이 도과)'
#   (2026910220·232·236·930032·930036·930039), 1쪽 표 '현재 전매제한 도과'·'(현재 전매 가능)', '본 주택의 전매제한은 없습니다'(2026000185).
# 결과 {months: 개월(모르면 None), base: '당첨자 발표일'|'YYYY-MM-DD'(최초 당첨자발표일), registration: 그 안에 등기하면 풀림, until_reg: 등기 때까지(기간 상한 없음), passed: 이미 지남, none: 없음}
_D = r"\(?(?:최초당첨자발표일\()?[‘’']?((?:20)?\d\d)\.(\d{1,2})\.(\d{1,2})\.?(?:\([월화수목금토일]\))?\)?\)?"


def _rs_ymd(m, i: int) -> str:
    y = m.group(i)
    return f"{'20' + y if len(y) == 2 else y}-{int(m.group(i + 1)):02d}-{int(m.group(i + 2)):02d}"


def parse_resale(flat: str) -> Optional[dict]:
    """전매제한 기간. 본문 문장 → LH 표·문장 → 1쪽 '단지 주요정보' 표 순서. PDF 글자 순서가 뒤섞여 숫자가 뒤로 밀린 꼴('로부터개월6', '년(2025.12.10.)1')도 읽는다.
    확실하지 않으면 None (없음으로 추측하지 않는다)."""
    def mon(n, unit):
        return int(n) * (12 if unit == "년" else 1)
    reg = r"(\(?단,?\d{1,2}년내소유권이전등기시해제\)?|\(단,소유권이전등기를완료한경우소유권이전등기를완료한때까지\))?"
    gone = r"(적용되어현재전매제한기간이도과|경과하여현재전매제한기간이도과|적용되어,?본입주자모집공고일현재해당전매제한기간은이미경과|이경과하여현재전매가가?능|적용)"
    head = r"전매제한(?:기간)?은?(?:최초)?입주자모집공고의당첨자발표일"
    pats = [
        # 재공급·무순위 문장
        (head + _D + r"(?:로부터|부터)(\d{1,2})(년|개월)(?:간)?" + reg + gone,
         lambda m: {"months": mon(m.group(4), m.group(5)), "base": _rs_ymd(m, 1), "registration": bool(m.group(6)), "passed": m.group(7) != "적용"}),
        (head + _D + r"(?:로부터|부터)년간적용되어현재전매제한기간이도과",   # 2026930036·037 숫자가 빠짐 — 기간은 모르지만 지났다는 것은 확실
         lambda m: {"months": None, "base": _rs_ymd(m, 1), "passed": True}),
        (head + r"로부터" + _D + r"년간적용됩니다\(?단,?년내소유권이전등기시해제(\d{1,2})",   # 2026910246 뒤섞임
         lambda m: {"months": mon(m.group(4), "년"), "base": _rs_ymd(m, 1), "registration": True, "passed": False}),
        (r"전매제한은■?최초입주자모집공고의당첨자발표일로부터년간\(?단,?년내소유권이전등기시해제\)?적용됩니다" + _D + r"(\d{1,2})",   # 2026910251 뒤섞임
         lambda m: {"months": mon(m.group(4), "년"), "base": _rs_ymd(m, 1), "registration": True, "passed": False}),
        # 민영 표준 표 '전매제한기간 …'
        (r"전매제한기간(?:은|:)?(?:해당주택의입주자로선정된날로부터|(?:최초)?당첨자발표일" + _D + r"(?:로부터)?|(?:최초)?당첨자발표일(?:로부터)?)?(\d{1,2})(년|개월)" + reg,
         lambda m: {"months": mon(m.group(4), m.group(5)), "base": _rs_ymd(m, 1) if m.group(1) else "당첨자 발표일", "registration": bool(m.group(6))}),
        (r"전매제한기간(?:최초)?당첨자발표일로부터(개월|년)(\d)",   # 2026000436·146 '로부터개월6'
         lambda m: {"months": mon(m.group(2), m.group(1)), "base": "당첨자 발표일"}),
        (r"구분(?:특별공급)?일반공급전매제한기간(개월|년)(\d{1,2})(?![\d,.])",   # 2026000471 표 '구분 일반공급 전매제한기간 개월 6' 뒤섞임 (단지 주요정보 표도 '개월 6')
         lambda m: {"months": mon(m.group(2), m.group(1)), "base": "당첨자 발표일"}),
        (r"전매제한기간최초당첨자발표일로부터년" + _D + r"(\d)",   # 2026910006 '년(2025.12.10.)1'
         lambda m: {"months": mon(m.group(4), "년"), "base": _rs_ymd(m, 1)}),
        (r"전매제한은최초당첨자발표일로부터(개월|년)적용됩니다" + _D + r"(\d)",   # 2026000046
         lambda m: {"months": mon(m.group(5), m.group(1)), "base": _rs_ymd(m, 2)}),
        (r"전매제한기간소유권이전등기일까지,?\(?다만,?그기간이(\d{1,2})?년을초과하는경우(?:\d{1,2}년\)|년\(,(\d)\d\))",
         lambda m: {"months": mon(m.group(1) or m.group(2), "년"), "base": "당첨자 발표일", "registration": True}),
        (r"전매제한기간소유권이전등기(?:시|일)까지|전매제한재당첨제한거주의무기간분양가상한제택지유형소유권이전등기시까지",
         lambda m: {"months": None, "base": "당첨자 발표일", "until_reg": True}),
        (r"전매제한기간(?:전매)?(?:제한)?(?:해당)?없음|본주택의전매제한은없습니다|규정에의거전매제한에해당되지않습니다|재당첨제한전매제한거주의무기간분양가상한제(?:택지유형)?(?:없음|\d{1,2}년)없음(?:없음|[1-5]년)(?:적용|미적용)",
         lambda m: {"months": 0, "none": True}),
        (r"전매(?:행위)?\(부부공동명의포함\)가불가",   # 이익공유형 분양주택(공공주택 특별법 제49조의10) — 전매 대신 공공에 되팔기(환매)
         lambda m: {"months": None, "forbidden": True}),
        # LH 표·문장
        (r"전매제한(?:최초)?당첨자발표일(\d{1,2})(년|개월)",
         lambda m: {"months": mon(m.group(1), m.group(2)), "base": "당첨자 발표일"}),
        (r"입주자로선정된날" + _D + r"로부터(\d{1,2})(년|개월)간?전매가금지",
         lambda m: {"months": mon(m.group(4), m.group(5)), "base": _rs_ymd(m, 1)}),
        (r"전매제한이(\d{1,2})(년|개월)적용",
         lambda m: {"months": mon(m.group(1), m.group(2)), "base": "당첨자 발표일"}),
        # 1쪽 표만 있는 무순위 '최초당첨자발표일(21.10.22.)로부터 3년간 적용되어 현재 전매제한기간 도과'
        (r"최초당[첨점]자발표일" + _D + r"로부터(\d{1,2})(년|개월)간?(적용되어현재전매제한기간도과|적용)?",
         lambda m: {"months": mon(m.group(4), m.group(5)), "base": _rs_ymd(m, 1), "passed": bool(m.group(6) and "도과" in m.group(6))}),
    ]
    for pat, fn in pats:
        if (m := re.search(pat, flat)):
            r = {"months": None, "base": None, "registration": False, "until_reg": False, "passed": False, "none": False, "forbidden": False, **fn(m), "m": m}
            # 재공급·무순위 '구분 특별공급 전매제한기간 최초 당첨자발표일로부터 1년간 적용되어 현재 전매제한기간 도과' (2026930041 — 예전엔 이번 당첨자 발표일부터
            # 1년으로 계산해 '1년 (~27.10.15)'로 보였다, 10-09 블라인드 대조): 바로 뒤 '도과'면 지남
            if not r["passed"] and re.match(r"간?(?:적용|부과)?되어,?현재전매(?:제한)?(?:기간|기관)?(?:이)?도과", flat[m.end():m.end() + 30]):
                r["passed"] = True
            return r
    return None


# ---- 청년 특별공급 기준 (기능 youth_special, 2026-10-05 사용자 '7 진행') ----
# 부모 기준은 부모(두 분)가 가진 자산 합계 — 2026000041 '② 신청자의 부모가 소유하고 있는 부동산·자동차·금융자산·일반자산가액의 총합에서 부채를 차감한 금액을 각각(본인·부모) 검증'.
# 공공주택 특별법 시행규칙 [별표 6의6] 가목 (이익공유형·토지임대부) 등: 19~39세·혼인 중 아님·과거 주택 소유 없음·무주택자(청년 본인, 세대원 집은 상관없음),
# 통장 6개월·6회, '제13조제3항에 따른 자산요건'(국토부 기준 — 공고문 <표2>), 본인 월평균소득 140% 이하. 금액은 공고문 표 그대로 읽는다:
#  2026000313·307 '(청년 특별공급은 신청자 본인 276,000천원 이하 및 부모 1,035,000천원 이하)', 출산가구 완화 '청년 특별공급의 경우, 본인 311,000천원 이하, 부모 …'(+10%p) · 345,000(+20%p),
#  '청년 특별공급 소득기준 1인 도시근로자 … 140% 5,338,708' (2026000041 '1인 청년 도시근로자 … 140% 5,338,708원')
def parse_youth(flat: str) -> Optional[dict]:
    if "청년특별공급" not in flat:
        return None
    out = {}
    m = re.search(r"청년특별공급(?:소득기준)?(?:1인)?도시근로자가구원수별가구당월평균소득액의140%(\d{1,2},\d{3},\d{3})", flat) or \
        re.search(r"1인청년(?:특별공급)?도시근로자가구원수별가구당월평균소득액의140%(\d{1,2},\d{3},\d{3})", flat)
    if m:
        out["income"] = int(m.group(1).replace(",", ""))
    m = re.search(r"청년특별공급은신청자본인(\d{2,3},\d{3})천원이하및부모(\d{1,2},\d{3},\d{3})천원이하", flat) or \
        re.search(r"\(본인\)(\d{2,3},\d{3})천원이하\(부모\)(\d{1,2},\d{3},\d{3})천원이하", flat)
    if m:
        out["self_asset"] = int(m.group(1).replace(",", "")) * 1000
        out["parent_asset"] = int(m.group(2).replace(",", "")) * 1000
    elif (m := re.search(r"청년(?:계층|특별공급)은신청자본인(\d{3})백만원이하및부모(\d{1,2},\d{3}|\d{3})백만원이하", flat)):   # SH 2026000041 '(청년계층은 신청자 본인 276백만원 이하 및 부모 1,035백만원 이하)'
        out["self_asset"] = int(m.group(1)) * 1_000_000
        out["parent_asset"] = int(m.group(2).replace(",", "")) * 1_000_000
    rx = [int(x.replace(",", "")) * 1000 for x in re.findall(r"청년특별공급의경우,본인(\d{2,3},\d{3})천원이하,부모\d{1,2},\d{3},\d{3}천원이하", flat)]
    if len(rx) == 2 and out.get("self_asset") and out["self_asset"] < rx[0] < rx[1]:
        out["self_asset_relax"] = rx   # 출산가구 +10%p, +20%p
    return out if ("income" in out and "self_asset" in out) else ({**out, "partial": True} if out else None)


def resale_cell(flat: str) -> Optional[int]:
    """1쪽 '단지 주요정보' 표의 전매제한 칸(개월). 칸이 '없음·N년·N개월'로 깔끔할 때만 — 본문과 대조하는 데 쓴다"""
    v = r"(없음|해당없음|\d{1,2}년|년\d{1,2}|\d{1,2}개월|개월\d{1,2})"
    m = re.search(r"재당첨제한전매제한거주의무기간분양가상한제(?:택지유형)?" + v + v + v + r"(?:적용|미적용|해당없음)", flat)
    if not m:
        return None
    c = m.group(2)
    if "없음" in c:
        return 0
    n = int(re.sub(r"\D", "", c))
    return n * (1 if "개월" in c else 12)


_SUMMARY = re.compile(r"전매제한\s*거주의무기간\s*분양가상한제\s*택지유형(.{0,400}?)(없음|[1-5]\s*년)\s*(?:\([^)]{0,60}\)\s*)?(적용|미적용)\s+(공공택지|민간택지)", re.S)


# 무순위(사후) 공고 1쪽 표는 '택지유형' 칸이 없다: '재당첨제한 전매제한 거주의무기간 분양가상한제 없음 최초 당첨자발표일(2026.09.01.)로부터 1년 없음 적용 구분'
# (2026910248 — 예전엔 못 읽어 청약홈 값 '미적용'이 남았다, 10-09 블라인드 대조). 마지막 두 칸(거주의무·분양가상한제) 바로 뒤가 '구분'/'공통'일 때만
_SUMMARY2 = re.compile(r"재당첨제한\s*전매제한\s*거주의무기간\s*분양가상한제\s+(?!택지유형)(.{0,200}?)\s(없음|[1-5]\s*년)\s+(적용|미적용)\s+(?:구분|\d?\s*공통)", re.S)


def _summary_table(text: str) -> Optional[dict]:
    """'단지 주요정보' 표의 거주의무기간·분양가상한제. 값 칸이 표 모양대로 이어지지 않으면(머리글 뒤 400자 안에 없으면) 읽지 않는다"""
    m = _SUMMARY.search(text) or _SUMMARY2.search(text)
    if not m:
        return None
    d = m.group(2).replace(" ", "")
    return {"residence_duty": 0 if d == "없음" else int(d[0]), "price_cap": m.group(3) == "적용", "quote": re.sub(r"\s+", " ", m.group(0))[:160], "mu": m.re is _SUMMARY2}

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
        return _sp_table_no_sum(t)
    # 머리글 낱말이 띄어 쓰인 공고문('기관 추천 다자녀 가구 신혼 부부 노부모 부양 생애 최초' — 2026930041)도 읽게 공백을 빼고 찾는다
    heads = [SP_NAMES[w] for w in re.findall("|".join(sorted(SP_NAMES, key=len, reverse=True)), h.group(1).replace(" ", ""))]
    if not heads or len(set(heads)) != len(heads):
        return None
    out = {}
    for m in re.finditer(r"\b0\d (\d{2,3}\.\d{4}[A-Z]{0,2}) \S+ ((?:(?!0\d \d{2,3}\.\d{4})[\d.,]+ |- ){7,14})", t[h.start():h.start() + 3000]):
        nums = m.group(2).split()
        vals = nums[6:]
        if len(vals) == len(heads) + 1 and not re.search(r"계|일반공급", h.group(1).split("소계")[-1]):
            # '계'·'일반공급' 칸이 없는 표 (2026930039 탕정 '총공급 세대수 특별공급 세대수 … 소계 생애최초 · 59A … 2 2') — 모두 특별공급일 때만(총공급 = 특공 합)
            cnt = lambda v: 0 if v == "-" else int(v) if v.isdigit() else None
            total, per = cnt(vals[0]), [cnt(v) for v in vals[1:]]
            if None in per or total is None or sum(per) != total:
                continue
            row = dict(zip(heads, per)); row["total"] = total
            out[m.group(1)] = row
            continue
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


def _sp_table_no_sum(t: str) -> Optional[dict]:
    """특공 '계' 칸이 없는 공급대상 표 (2026-10-05 주간 블라인드 표본 W41: 고양 장항 아테라 2026930038 불법행위 재공급)
    '… 총공급 세대수 노부모 부양 특별공급 일반공급 … 2026930038 01 084.9958A 84A 84.9958 24.3167 109.3125 51.6380 160.9505 53.0747 4 3 1'
    행 = 면적 6개 → 총공급 → 머리글 순서의 특공 유형별 세대 → 일반공급. 총공급 = 특공 합 + 일반공급 일 때만 받는다(추측 금지)."""
    h = re.search(r"총공급 ?세대수 ((?:(?:다자녀 ?가구|다자녀|신혼 ?부부|노부모 ?부양|생애 ?최초|신생아|기관 ?추천) ?)+)특별공급 ?일반공급(.{0,120}?)(20\d{8}) 01 ", t)
    if not h:
        return None
    head = h.group(1).replace(" ", "")
    heads = [SP_NAMES[w] for w in re.findall("|".join(sorted(SP_NAMES, key=len, reverse=True)), head)]
    if not heads or len(set(heads)) != len(heads):
        return None
    out = {}
    for m in re.finditer(r"\b0\d (\d{2,3}\.\d{4}[A-Z]{0,2}) \S+ ((?:(?!0\d \d{2,3}\.\d{4})[\d.,]+ |- ){7,14})", t[h.start():h.start() + 3000]):
        vals = m.group(2).split()[6:]
        if len(vals) != len(heads) + 2:
            continue
        cnt = lambda v: 0 if v == "-" else int(v) if v.isdigit() else None
        total, per, gen = cnt(vals[0]), [cnt(v) for v in vals[1:1 + len(heads)]], cnt(vals[-1])
        if None in per or gen is None or total is None or sum(per) + gen != total:
            continue
        row = dict(zip(heads, per))
        row["total"] = sum(per)
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
    # 기본 규칙(앞 40자 안 첫 금액)에 더해, '부동산(건물+토지)' 바로 뒤에 이어지는 칸들(출산가구 완화 표 한 줄 '237,050천원 이하 258,600천원 이하 215,500천원 이하')과
    # 줄이 바뀐 '부동산\n(건물+토지)\n215,500천원 이하'도 읽는다 — 첫 칸만 읽어 기본 기준을 놓치고 '앱 기준이 공고문에 없음'으로 잘못 경고했다 (2026-10-09 익산 부송에코르 2026000402)
    tw = re.sub(r"\s+", " ", text)
    run = lambda pat: {int(v.replace(",", "")) for m in re.finditer(pat, tw) for v in re.findall(r"([\d,]+)천원", m.group(1))}
    re_loose = {int(x.replace(",", "")) for x in re.findall(r"부동산[^\n]{0,40}?([\d]{2,3},\d{3})천원\s?이하", t)}
    car_loose = {int(x.replace(",", "")) for x in re.findall(r"자동차[^\n]{0,40}?([\d]{2},\d{3})천원\s?이하", t)}
    assets = {"부동산": sorted(re_loose | run(r"부동산\s?\(\s?건물\s?\+\s?토지\s?\)\s?((?:\d{2,3},\d{3}천원\s?이하\s?){1,4})")),
              "자동차": sorted(car_loose | run(r"자동차\s?((?:\d{2},\d{3}천원\s?이하\s?){1,4})")),
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
        # '못 읽음' 표시({'unknown': True})는 값이 없는 것으로 본다 — 예전엔 이 표시가 두 번째 도구의 값을 막았다 (2026-10-03 가점제·추첨제 비율)
        if (not found.get(k) or found.get(k) == {"unknown": True}) and alt.get(k) and alt.get(k) != {"unknown": True}:
            found[k] = alt[k]
            notes.append(f"{k} (첫 도구는 못 읽음)")
    return notes
