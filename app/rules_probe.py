"""청약 자격 규정 원문 모으기 (자격 판정 기능을 만들기 전 근거 확보용, 일회성).

모집공고문은 그 공고에 적용되는 청약 자격(1순위 가입기간·예치금·가점·특별공급 소득 기준 등)을
법령에 따라 적어 둔다. 여러 공고문에서 해당 문단을 뽑아 docs/rules-evidence.txt 에 남기고,
사람이 원문과 대조해 자격 판정 규칙의 근거로 쓴다.

    python -m app.rules_probe
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from .notice_pdf import UA, pdf_text

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


def main() -> None:
    rows = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    seen, lines = set(), []
    http = httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=True, headers=UA)
    for x in rows:
        pdf = x.get("notice_pdf")
        if not pdf or pdf in seen:
            continue
        seen.add(pdf)
        head = f"### {x['name']} · {x.get('house_dtl') or x['category']} · {x.get('sido')} {x.get('district')} · 공고일 {x.get('notice')} · 주택관리번호 {x['id'].split('-')[0]}"
        try:
            r = http.get(pdf)
            text = pdf_text(r.content) if r.status_code == 200 else ""
        except Exception as e:
            lines += [head, f"(PDF 실패: {e.__class__.__name__})", ""]
            continue
        lines += [head, f"PDF: {pdf} · {len(text)}자", ""]
        for w in KEYWORDS:
            for sn in windows(text, w):
                lines.append(f"[{w}] …{sn}…")
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {OUT} ({len(seen)}개 공고문)")


if __name__ == "__main__":
    main()
