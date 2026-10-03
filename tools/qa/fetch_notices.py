"""MASTER QA 원문 대조용 공고문 받기 (2026-10-02). evidence/qa/notice-ids.txt 의 주택관리번호마다 청약홈 공고 페이지 → 모집공고문 PDF 글을
evidence/qa/notices/<번호>.txt 로 남긴다(이미 있으면 건너뜀). 서비스 데이터는 건드리지 않는다. 실행: python -m tools.qa.fetch_notices"""
import json
from pathlib import Path

import httpx

from app import lh, notice_pdf

ROOT = Path(__file__).resolve().parents[2]
IDS = ROOT / "evidence" / "qa" / "notice-ids.txt"
OUT = ROOT / "evidence" / "qa" / "notices"   # 서비스 근거(evidence/notices, 지금 공고)와 섞지 않는다 — 그 폴더 전체를 도는 테스트가 있음
LIVE = ROOT / "evidence" / "notices"
ARC = ROOT / "docs" / "archive" / "past.json"


def main() -> None:
    ids = [l.strip() for l in IDS.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    arc = {}
    for x in json.loads(ARC.read_text(encoding="utf-8"))["items"]:
        arc.setdefault(x["notice_no"], x)
    cur = {}
    try:
        d = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
        for L in (d["listings"] if isinstance(d, dict) else d):
            cur.setdefault(L["id"].split("-")[0], {**L, "notice_no": L["id"].split("-")[0]})
    except Exception:
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    log = []
    for no in ids:
        f = OUT / f"{no}.txt"
        if f.exists() or (LIVE / f"{no}.txt").exists():
            log.append(f"{no} 있음")
            continue
        x = arc.get(no) or cur.get(no)   # 지금 공고도 받는다 (2026-10-03 사용자 제보 공고 원문 대조)
        if not x or not x.get("url"):
            log.append(f"{no} 보관함에 없음")
            continue
        text, msg, pdf = notice_pdf.fetch_notice_text(x["url"])
        if not text and x.get("house_dtl") == "국민":   # LH 공고는 청약홈에 PDF 가 없어 LH청약플러스에서 받는다 (app/lh.py, 2026-10-02)
            try:
                with httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=True, headers=notice_pdf.UA) as http:
                    raw, msg2, pdf = lh.fetch_lh_notice(x["name"].strip(), http)
                text = notice_pdf.pdf_text(raw) if raw else None
                msg = msg2 if not raw else msg
            except Exception as e:
                msg = f"LH 실패 {e.__class__.__name__}"
        if not text:
            log.append(f"{no} 실패 {msg[:80]}")
            continue
        head = f"### {x['name'].strip()} · {x.get('house_dtl') or x['category']} · {x.get('sido')} {x.get('district')} · 공고일 {x.get('notice')} · 주택관리번호 {no}"
        f.write_text(head + "\nPDF: " + str(pdf) + "\n" + text, encoding="utf-8")
        log.append(f"{no} 받음 {len(text)}자")
    (ROOT / "evidence" / "qa" / "fetch-notices.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
