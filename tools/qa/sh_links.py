"""SH 공고 화면 링크 점검 (CLAUDE.md 5: 출처 링크는 실제로 열어 숫자가 보이는지 확인한 뒤 쓴다).

docs/sh-rental.json 의 공고 몇 건에 대해, 쿠키 없는 새 연결로(사용자가 처음 누르는 것처럼)
  - url(PC 공고 화면)·url_mobile(모바일 공고 화면)이 열리고 제목이 보이는지
  - notice_pdf(공고문 내려받기 주소)를 바로 열면 PDF 가 오는지, 그 PDF 글에 수집한 접수 기간 문구가 있는지
를 evidence/qa/sh-links.txt 에 남긴다. 실행: python -m tools.qa.sh_links (Actions 'SH 임대 원천 점검')
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "sh-links.txt"
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"}


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def main() -> int:
    d = json.loads((ROOT / "docs" / "sh-rental.json").read_text(encoding="utf-8"))
    picks = [n for n in d["notices"] if n.get("schedule")][:3] + [n for n in d["notices"] if not n.get("schedule")][:1]
    log = [f"SH 링크 점검 · 공고 {len(picks)}건 · 쿠키 없는 새 연결"]
    for n in picks:
        log.append(f"\n[{n['id']}] {n['name'][:50]}")
        for k in ("url", "url_mobile"):
            with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as c:
                try:
                    r = c.get(n[k])
                    title = squash(n["name"])[:20]
                    log.append(f"  {k}: HTTP {r.status_code} · {len(r.text)}자 · 제목 보임 {title in squash(r.text)} · 최종 주소 {str(r.url)[:120]}")
                except Exception as e:  # noqa: BLE001
                    log.append(f"  {k}: 실패 {type(e).__name__}")
        if n.get("notice_pdf"):
            with httpx.Client(headers=UA, timeout=60, follow_redirects=True) as c:
                try:
                    r = c.get(n["notice_pdf"])
                    pdf = r.content[:5] == b"%PDF-"
                    line = f"  notice_pdf 바로 열기: HTTP {r.status_code} · {r.headers.get('content-type', '')} · {len(r.content)}바이트 · PDF {pdf}"
                    if pdf and n.get("schedule"):
                        from pypdf import PdfReader
                        txt = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages)
                        q = squash(n["schedule"][0].get("quote", ""))[:30]
                        line += f" · 접수 문구 보임 {q in squash(txt)} ({n['schedule'][0]['apply_start']}~{n['schedule'][0]['apply_end']})"
                    log.append(line)
                except Exception as e:  # noqa: BLE001
                    log.append(f"  notice_pdf: 실패 {type(e).__name__}")
    OUT.write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
