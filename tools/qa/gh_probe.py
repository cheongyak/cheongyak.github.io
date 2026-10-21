"""GH(경기주택도시공사) 임대 공고 원천 점검 (2026-10-21 사용자 'GH 임대 추가' — 조사 단계, 화면·판정에는 쓰지 않음).
공공데이터 API 가 없어 GH 청약센터(apply.gh.or.kr)·GH 누리집(www.gh.or.kr) 화면을 GitHub Actions 서버에서 받을 수 있는지, 공고 목록이 어디에 어떤 모양으로 있는지 본다.
첫 화면에서 '공고·모집·임대' 글자가 있는 같은 사이트 링크를 모아 두 단계까지 받아 evidence/qa/gh/ 에 HTML 을 남기고, 요약을 evidence/qa/gh-probe.txt 에.
실행: python -m tools.qa.gh_probe (Actions 'GH 임대 원천 점검')"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "gh-probe.txt"
RAW = ROOT / "evidence" / "qa" / "gh"
NOW = datetime.now(timezone(timedelta(hours=9)))
STARTS = ["https://apply.gh.or.kr/", "https://www.gh.or.kr/"]
HOSTS = {"apply.gh.or.kr", "www.gh.or.kr", "gh.or.kr"}
WORD = re.compile(r"공고|모집|임대|청약|입주자")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36 cheongyakpass-probe",
      "Accept-Language": "ko-KR,ko;q=0.9"}
strip = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def links(page: str, base: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r'<a\b([^>]*)>(.*?)</a>', page, re.S | re.I):
        attrs, txt = m.group(1), strip(m.group(2))
        h = re.search(r'href="([^"#]+)"', attrs)
        oc = re.search(r'onclick="([^"]+)"', attrs)
        if h and not h.group(1).lower().startswith("javascript"):
            out.append((urljoin(base, html.unescape(h.group(1))), txt))
        elif oc or (h and h.group(1).lower().startswith("javascript")):
            out.append(("JS:" + html.unescape((oc or h).group(1))[:200], txt))
    return out


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    rep = [f"GH 원천 점검 {NOW:%Y-%m-%d %H:%M}"]
    seen, queue, n = set(), [(u, 0) for u in STARTS], 0
    with httpx.Client(headers=UA, timeout=25, follow_redirects=True, verify=True) as c:
        while queue and n < 40:
            url, depth = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                r = c.get(url)
            except Exception as e:
                rep.append(f"[실패] {url} {e.__class__.__name__}: {e}")
                continue
            n += 1
            body = r.text
            f = RAW / f"{n:02d}.html"
            f.write_text(f"<!-- {url} -> {r.url} {r.status_code} -->\n" + body[:400_000], encoding="utf-8")
            ls = links(body, str(r.url))
            rep.append(f"\n[{n:02d}] {url} → {r.url} · {r.status_code} · {len(body):,}자 · 제목 {strip((re.search(r'<title>(.*?)</title>', body, re.S) or [None, ''])[1])[:60]}")
            for u, t in ls:
                if WORD.search(t) or WORD.search(u):
                    rep.append(f"    {t[:40]} → {u[:200]}")
            forms = re.findall(r'<form[^>]*action="([^"]+)"', body, re.I)
            if forms:
                rep.append("    form: " + " | ".join(forms[:5]))
            ajax = sorted(set(re.findall(r'["\'](/[A-Za-z0-9_/\-]+\.(?:do|json|ajax))["\']', body)))
            if ajax:
                rep.append("    스크립트 주소: " + " ".join(ajax[:40]))
            if depth < 2:
                for u, t in ls:
                    if u.startswith("JS:"):
                        continue
                    if urlparse(u).hostname in HOSTS and (WORD.search(t) or re.search(r"pbanc|notice|bbs|brd|board|rcrt|rent|imdae", u, re.I)):
                        queue.append((u, depth + 1))
    OUT.write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep[:80]))


if __name__ == "__main__":
    main()
