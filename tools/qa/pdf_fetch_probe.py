"""공고문 PDF 받기 실패 원인 점검 (2026-10-03). docs/listings.json 에서 공고문을 못 읽은 공고(또는 인자로 준 주택관리번호)마다
청약홈 공고 화면의 첨부 링크를 여러 방식(그대로·Referer·www 주소·첨부 순번 바꾸기·잠시 뒤 다시)으로 받아 보고
응답 코드·크기·앞 글자를 evidence/qa/pdf-fetch-probe.txt 에 남긴다. 서비스 데이터는 건드리지 않는다.
실행: python -m tools.qa.pdf_fetch_probe [주택관리번호 ...]"""
import json
import re
import sys
import time
from pathlib import Path

import httpx

from app import notice_pdf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "pdf-fetch-probe.txt"
PAGE = "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo={n}&pblancNo={n}"


def failed_ids() -> list[str]:
    d = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    Ls = d["listings"] if isinstance(d, dict) else d
    return sorted({L["id"].split("-")[0] for L in Ls if not L.get("sample") and not L.get("notice_pdf") and L.get("url")})


def desc(r) -> str:
    c = r.content
    kind = "PDF" if c[:4] == b"%PDF" else "HWP" if c[:4] == bytes.fromhex("d0cf11e0") else "ZIP" if c[:2] == b"PK" else "HTML/글" if b"<" in c[:200] or len(c) < 400 else "기타"
    snip = c[:100].decode("utf-8", "replace").replace("\n", " ") if kind != "PDF" and len(c) < 2000 else ""
    hd = {k: r.headers.get(k) for k in ("content-type", "content-disposition", "content-length", "server") if r.headers.get(k)}
    return f"{r.status_code} {len(c)}바이트 {kind} {hd} {snip}"


def main() -> None:
    ids = sys.argv[1:] or failed_ids()
    http = httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=True, headers=notice_pdf.UA)
    out = [f"# 공고문 PDF 받기 점검 {time.strftime('%Y-%m-%d %H:%M')} · 대상 {', '.join(ids) or '없음'}"]
    for n in ids:
        page = PAGE.format(n=n)
        try:
            r = http.get(page)
        except Exception as e:
            out.append(f"\n## {n} 공고 화면 실패 {e.__class__.__name__}")
            continue
        html = r.text
        links = notice_pdf.find_pdf_links(html, str(r.url))
        out.append(f"\n## {n} 공고 화면 {r.status_code} {len(html)}자 · 첨부 링크 {len(links)}개")
        # 첨부 부분 화면 글(파일 이름·버튼) 그대로
        for m in re.finditer(r"(?s).{0,300}(?:[Aa]tchmnfl|첨부|모집공고문).{0,300}", html):
            out.append("  [화면] " + re.sub(r"\s+", " ", m.group(0))[:600])
            if len(out) > 400:
                break
        for link in links[:6]:
            out.append(f"  링크 {link}")
            tries = [("그대로", link, {}), ("Referer", link, {"Referer": str(r.url)}),
                     ("www 주소", link.replace("static.applyhome.co.kr", "www.applyhome.co.kr"), {"Referer": str(r.url)})]
            m = re.search(r"atchmnflSn=(\d+)", link)
            if m:
                for sn in range(1, 9):
                    if str(sn) != m.group(1):
                        tries.append((f"순번 {sn}", re.sub(r"atchmnflSn=\d+", f"atchmnflSn={sn}", link), {"Referer": str(r.url)}))
            for name, u, h in tries:
                try:
                    p = http.get(u, headers={**notice_pdf.UA, **h})
                    out.append(f"    {name}: {desc(p)}")
                except Exception as e:
                    out.append(f"    {name}: 실패 {e.__class__.__name__}")
        text, msg, pdf = notice_pdf.fetch_notice_text(page, http)
        out.append(f"  지금 서비스 방식으로 받기: {msg[:300]}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
