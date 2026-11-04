"""검색엔진·광고 심사용 정적 페이지 검사 (기능 seo_content, 2026-11-04).

docs/ 아래 정적 페이지를 모두 읽어 본다:
  ① 산문 길이: <main> 글자에서 표·구조화 데이터·이동 경로를 뺀 글자 수 — 지금 공고 페이지·가이드 1,500자 이상
  ② 금지어: 무조건·꼭 넣으세요·당첨 가능성 높아요·추천 ('기관추천' 제도 이름·'비추천' 등급 이름은 뺌)
  ③ 깨진 내부 링크 0: href="/…" 가 docs 안 파일로 이어지는지 (앱 주소 /#/… 는 앱 화면이라 뺌)
  ④ 구조화 데이터(JSON-LD)가 JSON 으로 읽히는지, 공고 페이지에 FAQPage·BreadcrumbList 가 있는지
  ⑤ sitemap.xml 에 모든 페이지가 있는지, lastmod 가 있는지
사용: python -m tools.qa.seo_static [--json evidence/qa/seo-static.json]
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
FORBID = re.compile(r"무조건|꼭 넣으세요|당첨 가능성(이)? ?(높|크)|(?<!기관)(?<!비)추천")
SKIP_DIRS = {"bot", "chat-notice", "archive"}
MIN_PROSE = 1500


def prose(s: str) -> str:
    m = re.search(r"<main>(.*)</main>", s, re.S)
    t = m.group(1) if m else s
    t = re.sub(r"<table.*?</table>", " ", t, flags=re.S)
    t = re.sub(r"<script.*?</script>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def pages() -> list[Path]:
    out = []
    for p in DOCS.rglob("index.html"):
        rel = p.relative_to(DOCS)
        if rel.parts[0] in SKIP_DIRS or str(rel) == "index.html":
            continue
        out.append(p)
    return sorted(out)


def kind(rel: str) -> str:
    if rel.startswith("notice/type/"):
        return "notice_type"
    if re.match(r"notice/\d+/", rel):
        return "notice"
    if rel.startswith("notice/"):
        return "notice_list"
    if re.match(r"rental/[a-z]+/[^/]+/", rel):
        return "rental"
    if rel.startswith("rental/"):
        return "rental_list"
    if rel.startswith("guide/") and rel != "guide/index.html":
        return "guide"
    return "other"


def link_ok(href: str) -> bool:
    u = urlparse(href)
    if u.scheme or u.netloc or not href.startswith("/") or href.startswith("/#"):
        return True
    path = unquote(u.path)
    f = DOCS / path.lstrip("/")
    return (f / "index.html").exists() if path.endswith("/") else f.exists() or (f / "index.html").exists()


def run() -> dict:
    res = {"pages": 0, "by_kind": {}, "short": [], "forbidden": [], "broken": [], "ld_bad": [], "ld_missing": [], "not_in_sitemap": [], "prose_min": {}, "live_notice_prose": []}
    sm = (DOCS / "sitemap.xml").read_text(encoding="utf-8") if (DOCS / "sitemap.xml").exists() else ""
    locs = {unquote(x) for x in re.findall(r"<loc>https://cheongyakpass\.kr/([^<]*)</loc>", sm)}
    no_lastmod = sm.count("<url>") - sm.count("<lastmod>")
    for p in pages():
        rel = str(p.relative_to(DOCS))
        s = p.read_text(encoding="utf-8")
        k = kind(rel)
        res["pages"] += 1
        res["by_kind"][k] = res["by_kind"].get(k, 0) + 1
        t = prose(s)
        n = len(t)
        res["prose_min"][k] = min(res["prose_min"].get(k, 10 ** 9), n)
        live = k == "notice" and "접수 마감" not in s
        if k == "notice" and live:
            res["live_notice_prose"].append(n)
        if (live or k == "guide") and n < MIN_PROSE:
            res["short"].append(f"{rel} {n}자")
        bad = [m.group(0) for m in FORBID.finditer(t)]
        if bad:
            res["forbidden"].append(f"{rel} {sorted(set(bad))}")
        for h in re.findall(r'href="([^"]+)"', s):
            if not link_ok(html.unescape(h)):
                res["broken"].append(f"{rel} → {h}")
        lds = re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
        types = set()
        for x in lds:
            try:
                types.add(json.loads(x).get("@type"))
            except Exception:
                res["ld_bad"].append(rel)
        if k == "notice" and not {"FAQPage", "BreadcrumbList"} <= types and "seo-content" not in res:
            res["ld_missing"].append(rel)
        slug = rel[: -len("index.html")]
        if slug not in locs:
            res["not_in_sitemap"].append(slug)
    res["sitemap_urls"] = len(locs)
    res["sitemap_no_lastmod"] = no_lastmod
    res["ok"] = not (res["short"] or res["forbidden"] or res["broken"] or res["ld_bad"] or res["ld_missing"] or res["not_in_sitemap"] or no_lastmod)
    return res


if __name__ == "__main__":
    r = run()
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    ln = r["live_notice_prose"]
    print(f"[정적 페이지 검사] {r['pages']}쪽 {r['by_kind']} · 지금 공고 산문 최소 {min(ln) if ln else '-'}자 · 짧음 {len(r['short'])} · 금지어 {len(r['forbidden'])} · 깨진 링크 {len(r['broken'])} · "
          f"구조화 데이터 오류 {len(r['ld_bad'])}·빠짐 {len(r['ld_missing'])} · sitemap 빠짐 {len(r['not_in_sitemap'])} · {'통과' if r['ok'] else '실패'}")
    for k in ("short", "forbidden", "broken", "ld_bad", "ld_missing", "not_in_sitemap"):
        for x in r[k][:8]:
            print(f"  [{k}] {x}")
    sys.exit(0 if r["ok"] else 1)
