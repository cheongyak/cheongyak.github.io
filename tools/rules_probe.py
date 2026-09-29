"""청약 자격 규정 원문 모으기 (자격 판정 기능을 만들기 전 근거 확보용, 일회성).

모집공고문은 그 공고에 적용되는 청약 자격(1순위 가입기간·예치금·가점·특별공급 소득 기준 등)을
법령에 따라 적어 둔다. 여러 공고문에서 해당 문단을 뽑아 docs/rules-evidence.txt 에 남기고,
사람이 원문과 대조해 자격 판정 규칙의 근거로 쓴다.

    python -m tools.rules_probe
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from app.notice_pdf import UA, pdf_text


def pdf_text_all(data: bytes) -> str:
    from io import BytesIO
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(data)).pages)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "rules-evidence.txt"
KEYWORDS = ["예치기준금액", "예치금액", "청약예금", "가입기간", "납입인정", "1순위", "가점제", "무주택기간", "부양가족",
            "추첨제", "신혼부부", "생애최초", "다자녀", "노부모", "신생아", "기관추천", "월평균소득", "소득기준", "자산",
            "우선공급", "거주기간", "재당첨", "5년 이내", "2주택"]
WIDTH = 700
PER_WORD = 2


def windows(text: str, word: str) -> list[str]:
    out, pos = [], 0
    flat = re.sub(r"\s+", " ", text)
    while len(out) < PER_WORD:
        i = flat.find(word, pos)
        if i < 0:
            break
        out.append(flat[max(0, i - 150): i + WIDTH])
        pos = i + WIDTH
    return out


EVIDENCE = ROOT / "evidence"   # 공고문 전문(사이트에는 올라가지 않는 폴더). 규칙을 원문과 대조할 때 쓴다


def probe_pages(rows: list, http: httpx.Client) -> None:
    """공고문 PDF 를 못 찾은 공고(주로 LH 공공분양)의 청약홈 화면에서 링크를 모아 둔다 → PDF 를 어디서 받을지 근거"""
    seen = set()
    for x in rows:
        nid = x["id"].split("-")[0]
        if x.get("notice_pdf") or nid in seen or not x.get("url"):
            continue
        seen.add(nid)
        out = [f"{x['name']} · {x.get('house_dtl')} · {x['url']}"]
        try:
            r = http.get(x["url"])
            html = r.text
            out.append(f"응답 {r.status_code} · {len(html)}자")
            for m in re.finditer(r"""(?:href|onclick|src)\s*=\s*["']([^"']{4,300})["']""", html):
                v = m.group(1)
                if re.search(r"lh\.or\.kr|[Ff]ile|[Dd]own|[Aa]tch|pdf|hwp|popup|Popup|window\.open", v):
                    out.append(v)
            for m in re.finditer(r"https?://[^\s'\"<>]*lh\.or\.kr[^\s'\"<>]*", html):
                out.append(m.group(0))
        except Exception as e:
            out.append(f"실패: {e.__class__.__name__}")
        (EVIDENCE / "pages").mkdir(parents=True, exist_ok=True)
        (EVIDENCE / "pages" / f"{nid}.txt").write_text("\n".join(dict.fromkeys(out)) + "\n", encoding="utf-8")


LH_LIST = "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancList.do"


def probe_lh(rows: list, http: httpx.Client) -> None:
    """LH 청약플러스 공고 목록에서 공공분양 공고를 찾아 상세·첨부파일 링크 형태를 기록 (공고문 PDF 받는 방법 확인용)"""
    names = sorted({x["name"] for x in rows if x.get("house_dtl") == "국민" and not x.get("notice_pdf")})
    out = [f"대상: {names}"]
    for params in ({"mi": "1027"}, {"mi": "1027", "srchUppAisTpCd": "05"}, {"mi": "1026"}):
        try:
            r = http.get(LH_LIST, params=params)
            html = r.text
            out.append(f"== GET {params} → {r.status_code} · {len(html)}자 · 최종 주소 {r.url}")
            for m in re.finditer(r"""(?:href|onclick|data-[a-z-]+)\s*=\s*["']([^"']{4,300})["']""", html):
                v = m.group(1)
                if re.search(r"panId|pan_id|PAN_ID|selectWrtanc|lhFile|fileDown|Detail|detail", v):
                    out.append("  " + v)
            for n in names:
                key = re.sub(r"\(.*", "", n)[:8]
                i = html.find(key)
                out.append(f"  [{key}] " + (re.sub(r"\s+", " ", html[max(0, i - 400): i + 400]) if i >= 0 else "목록에 없음"))
        except Exception as e:
            out.append(f"== GET {params} 실패: {e.__class__.__name__} {e}")
    (EVIDENCE / "pages").mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "pages" / "lh-list.txt").write_text("\n".join(dict.fromkeys(out)) + "\n", encoding="utf-8")


def main() -> None:
    rows = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    seen, lines = set(), []
    http = httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=True, headers=UA)
    try:
        probe_lh(rows, http)
    except Exception as e:
        print(f"LH 점검 실패: {e}")
    try:
        probe_pages(rows, http)
    except Exception as e:
        print(f"페이지 점검 실패: {e}")
    for x in rows:
        pdf = x.get("notice_pdf")
        if not pdf or pdf in seen:
            continue
        seen.add(pdf)
        head = f"### {x['name']} · {x.get('house_dtl') or x['category']} · {x.get('sido')} {x.get('district')} · 공고일 {x.get('notice')} · 주택관리번호 {x['id'].split('-')[0]}"
        try:
            r = http.get(pdf)
            text = pdf_text_all(r.content) if r.status_code == 200 else ""
        except Exception as e:
            lines += [head, f"(PDF 실패: {e.__class__.__name__})", ""]
            continue
        lines += [head, f"PDF: {pdf} · {len(text)}자", ""]
        if text:
            (EVIDENCE / "notices").mkdir(parents=True, exist_ok=True)
            (EVIDENCE / "notices" / f"{x['id'].split('-')[0]}.txt").write_text(head + "\n" + text, encoding="utf-8")
        for w in KEYWORDS:
            for sn in windows(text, w):
                lines.append(f"[{w}] …{sn}…")
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {OUT} ({len(seen)}개 공고문)")


if __name__ == "__main__":
    main()
