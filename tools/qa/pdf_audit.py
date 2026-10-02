"""공고문 PDF 읽기 점검 (2026-10-02 사용자 '공고문에서 짧게 가져오는 등 은근히 잘못 가져오는 경우가 있다').

수집(app/notice_pdf)이 공고문을 제대로, 빠짐없이 읽는지 원본 PDF 로 따로 확인한다. 작업 환경에서는 청약홈에 접속할 수 없어 Actions(probe.yml)에서 돈다.
지금 공고마다:
  1. 공고 화면의 PDF 첨부를 모두 받는다 → 수집이 고르는 첨부(앞에서부터 글자 500자 넘는 첫 PDF)가 가장 긴 '모집공고문'인지
     (정정공고·팸플릿·짧은 안내문을 본문 대신 읽는지)
  2. 쪽수 · 수집이 읽는 쪽수(상한) · 쪽마다 글자 수 → 잘림, 글자가 없는 쪽(스캔 이미지 쪽)
  3. 필수 단원(신청자격·공급대상·당첨자 선정·재당첨·일정·계약 등)이 텍스트에 있는지
  4. 두 번째 읽기 도구(pypdfium2)로 같은 PDF 를 읽어 parse_notice 결과를 비교 → 한쪽만 읽히거나 값이 다른 항목
  5. 지금 수집 값(docs/listings.json)과 다시 읽은 값이 같은지
결과: evidence/qa/pdf-audit.json · 한 줄 요약. 서비스 데이터는 건드리지 않는다. 실행: python -m tools.qa.pdf_audit [--max 80]
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app import notice_pdf  # noqa: E402

OUT = ROOT / "evidence" / "qa" / "pdf-audit.json"
# 모집공고문이면 거의 반드시 있는 단원 (공급 종류별로 다르게 적는 말은 | 로)
SECTIONS = {
    "신청자격": r"신청\s*자격|청약\s*자격|입주자\s*자격",
    "공급대상·금액": r"공급\s*대상|공급\s*금액|공급\s*규모",
    "당첨자 선정": r"당첨자\s*선정|입주자\s*선정|당첨자\s*결정",
    "재당첨·제한": r"재당첨|전매\s*제한",
    "일정": r"당첨자\s*발표|청약\s*접수|접수\s*일",
    "계약": r"계약\s*체결|계약\s*장소|계약금",
}
KEYS = ["need_head", "price_cap", "residence_duty", "duty_silent", "rewin_years", "account_months", "deposit_count", "balance", "ext"]


def pages_pypdf(data: bytes) -> list[str]:
    from pypdf import PdfReader
    return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages]


def pages_pdfium(data: bytes) -> list[str] | None:
    try:
        import pypdfium2 as pdfium
    except Exception:
        return None
    doc = pdfium.PdfDocument(data)
    out = []
    for i in range(len(doc)):
        tp = doc[i].get_textpage()
        out.append(tp.get_text_range() or "")
    return out


def summarize(fields: dict) -> dict:
    o = {k: fields.get(k) for k in KEYS if k in fields}
    if fields.get("residence"):
        r = fields["residence"]
        o["residence"] = {"area": (r.get("area") or {}).get("name"), "months": r.get("months"), "since": r.get("since")}
    if fields.get("pub_limits"):
        o["pub_limits_kind"] = fields["pub_limits"].get("kind")
    if fields.get("schedule"):
        o["schedule"] = fields["schedule"]
    return o


def audit_notice(http: httpx.Client, url: str, listing: dict, cap: int, n_types: int = 1) -> dict:
    r = http.get(url)
    links = notice_pdf.find_pdf_links(r.text, str(r.url)) if r.status_code == 200 else []
    atts = []
    for link in links[:8]:
        try:
            p = http.get(link, headers={**notice_pdf.UA, "Referer": str(r.url)})
        except Exception as e:
            atts.append({"url": link, "error": e.__class__.__name__})
            continue
        if p.status_code != 200 or p.content[:4] != b"%PDF":
            atts.append({"url": link, "error": f"PDF 아님 ({p.status_code}, {len(p.content)}바이트)"})
            continue
        try:
            pp = pages_pypdf(p.content)
        except Exception as e:
            atts.append({"url": link, "error": f"pypdf 실패 {e.__class__.__name__}"})
            continue
        atts.append({"url": link, "bytes": len(p.content), "pages": len(pp), "chars": sum(map(len, pp)),
                     "head": re.sub(r"\s+", " ", "".join(pp[:1]))[:80], "_data": p.content, "_pp": pp})
    if not any("pages" in a for a in atts) and listing.get("house_dtl") == "국민":   # LH 공공분양은 청약홈 화면에 PDF 가 없어 수집도 LH청약플러스에서 받는다 (pipeline._fetch_text)
        from app import lh
        try:
            data, m2, url2 = lh.fetch_lh_notice(listing["name"], http)
            if data:
                pp = pages_pypdf(data)
                atts.append({"url": url2, "bytes": len(data), "pages": len(pp), "chars": sum(map(len, pp)), "head": re.sub(r"\s+", " ", "".join(pp[:1]))[:80], "_data": data, "_pp": pp, "via": "LH청약플러스"})
            else:
                atts.append({"url": "LH청약플러스", "error": m2})
        except Exception as e:
            atts.append({"url": "LH청약플러스", "error": e.__class__.__name__})
    pdfs = [a for a in atts if "pages" in a]
    out = {"notice": listing["id"].split("-")[0], "name": listing["name"], "url": url, "attachments": len(links), "pdfs": len(pdfs),
           "attachment_list": [{k: v for k, v in a.items() if not k.startswith("_")} for a in atts]}
    if not pdfs:
        out["problem"] = ["PDF 를 하나도 받지 못함"]
        return out
    # 수집이 고르는 첨부 = 앞에서부터 상한 안 글자 500자 넘는 첫 PDF (notice_pdf.fetch_notice_text)
    chosen = next((a for a in pdfs if sum(map(len, a["_pp"][:cap])) > 500), None)
    longest = max(pdfs, key=lambda a: a["chars"])
    probs = []
    if chosen is None:
        probs.append("글자가 있는 PDF 가 없음 (스캔 이미지 추정)")
        chosen = longest
    elif chosen is not longest and longest["chars"] > chosen["chars"] * 1.5:
        probs.append(f"수집이 고르는 첨부({chosen['pages']}쪽 {chosen['chars']}자 · '{chosen['head'][:30]}')보다 긴 PDF({longest['pages']}쪽 {longest['chars']}자 · '{longest['head'][:30]}')가 있음")
    pp = chosen["_pp"]
    text_read = "\n".join(pp[:cap])
    empty = [i + 1 for i, t in enumerate(pp) if len(t.strip()) < 30]
    out.update({"chosen": chosen["url"], "pages": len(pp), "pages_read": min(len(pp), cap), "chars_read": len(text_read), "empty_pages": empty[:30],
                "chars_per_page_min": min(map(len, pp)) if pp else 0})
    if len(pp) > cap:
        lost = sum(map(len, pp[cap:]))
        probs.append(f"{len(pp)}쪽 중 {cap}쪽까지만 읽음 — 뒤 {len(pp) - cap}쪽 {lost}자 빠짐")
    if empty:
        probs.append(f"글자가 거의 없는 쪽 {len(empty)}개 (스캔 이미지·표 그림 추정): {empty[:10]}")
    missing = [k for k, rx in SECTIONS.items() if not re.search(rx, text_read)]
    if missing:
        probs.append("필수 단원 못 찾음: " + ", ".join(missing))
    # 읽은 값: 지금 방식 vs 전체 쪽 vs 다른 도구
    a = summarize(notice_pdf.parse_notice(text_read))
    full = summarize(notice_pdf.parse_notice("\n".join(pp))) if len(pp) > cap else a
    pdfium = pages_pdfium(chosen["_data"])
    b = summarize(notice_pdf.parse_notice("\n".join(pdfium))) if pdfium else None
    out["fields"] = a
    if b is not None:   # 수집이 하는 것처럼 두 도구 값을 합친 결과 (기능 pdf_dual_read)
        merged = notice_pdf.parse_notice(text_read)
        notice_pdf.merge_alt(merged, notice_pdf.parse_notice("\n".join(pdfium)))
        out["fields_merged"] = summarize(merged)
    if full != a:
        out["fields_full"] = full
        probs.append("전체 쪽을 읽으면 값이 달라짐: " + ", ".join(sorted(k for k in set(a) | set(full) if a.get(k) != full.get(k))))
    if b is not None:
        diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        out["fields_pdfium"] = b
        out["pdfium_chars"] = sum(map(len, pdfium))
        if diff:
            out["tool_diff"] = {k: [a.get(k), b.get(k)] for k in diff}
            both = [k for k in diff if a.get(k) is not None and b.get(k) is not None]
            one = [k for k in diff if k not in both]
            if both:   # 둘 다 읽었는데 다름 → 수집은 데이터 확인 필요로 표시 (merge_alt conflicts)
                probs.append("읽기 도구에 따라 값이 다름: " + ", ".join(f"{k} {a.get(k)!r}↔{b.get(k)!r}"[:80] for k in both))
            if one:    # 한 도구만 읽음 → 수집은 다른 도구 값으로 채움 (정보)
                out["filled_by_second_tool"] = one
    # 지금 수집 값과
    ref = out.get("fields_merged") or a   # 수집과 같은 방식(두 도구 합침)으로 읽은 값과 비교
    live = {k: listing.get(k) for k in KEYS if k in ref and k in listing}
    gap = {k: [listing.get(k), ref.get(k)] for k in live if listing.get(k) != ref.get(k) and not (k == "residence_duty" and listing.get("price_cap") is False)
           and not (k == "ext" and n_types > 1)}   # 확장비는 주택형이 하나인 공고에만 쓴다 (pipeline) — 여러 주택형 공고의 차이는 정상
    gap = {k: v for k, v in gap.items() if v[0] != v[1]}
    if gap:
        out["live_gap"] = gap
        probs.append("지금 수집 값과 다시 읽은 값이 다름: " + ", ".join(f"{k} {v[0]!r}→{v[1]!r}" for k, v in gap.items()))
    out["problem"] = probs
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=80, help="수집이 읽는 쪽수 상한 (app/notice_pdf.PAGE_CAP)")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    cap = getattr(notice_pdf, "PAGE_CAP", a.max)
    data = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    rows = data["items"] if isinstance(data, dict) else data
    by = {}
    for x in rows:
        if x.get("url") and not x.get("sample"):
            by.setdefault(x["url"], x)
    http = httpx.Client(timeout=httpx.Timeout(40, connect=15), follow_redirects=True, headers=notice_pdf.UA)
    res, t0 = [], time.monotonic()
    for i, (url, x) in enumerate(by.items()):
        if a.limit and i >= a.limit:
            break
        if time.monotonic() - t0 > 1500:
            res.append({"notice": x["id"].split("-")[0], "name": x["name"], "skipped": "시간 제한"})
            continue
        try:
            res.append(audit_notice(http, url, x, cap, sum(1 for y in rows if y.get('url') == url)))
        except Exception as e:
            res.append({"notice": x["id"].split("-")[0], "name": x["name"], "error": f"{e.__class__.__name__}: {str(e)[:120]}"})
    bad = [r for r in res if r.get("problem")]
    kinds = {}
    for r in bad:
        for p in r["problem"]:
            k = re.sub(r"[\d,]+", "N", p.split(":")[0])[:50]
            kinds[k] = kinds.get(k, 0) + 1
    OUT.write_text(json.dumps({"date": date.today().isoformat(), "page_cap": cap, "notices": len(res), "with_problem": len(bad), "kinds": kinds,
                               "errors": [r for r in res if r.get("error") or r.get("skipped")], "results": res}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[QA 공고문 읽기] 공고 {len(res)}개 · 문제 의심 {len(bad)}개 · " + " · ".join(f"{k} {n}" for k, n in sorted(kinds.items(), key=lambda t: -t[1])))
    for r in bad[:12]:
        print("  ", r["notice"], r["name"][:16], "|", " / ".join(r["problem"])[:220])
    return 0


if __name__ == "__main__":
    sys.exit(main())
