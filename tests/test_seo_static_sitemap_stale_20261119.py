"""2026-11-19 아침 손 수집(run 44402034641) 실패: 처음 시험 test_generated_pages_pass_checks 가
'오래된 마감 공고인데 sitemap 에 있음'(2026000444·2026930033, 당첨자 발표 10-19)으로 실패.
sitemap 은 전날(11-18) 실행이 만든 것이고, 날짜가 11-19 로 바뀌며 두 공고가 마감 뒤 30일을 막 넘겼을 뿐.

- 마지막 일정 뒤 30일째(포함): sitemap 에 있어야 함 → 있으면 정상
- 31일째 + 전날 만든 sitemap 에 남음: 실패가 아니라 sitemap_stale 로만
- 32일째 이상 남음: 그대로 실패 (빼는 기능이 고장 난 것)
- 있어야 할 페이지가 sitemap 에 없음: 그대로 실패
- 공고 자료 계산 실패: 조용히 넘기지 않고 warnings 에 남김
"""
from collections import OrderedDict
from datetime import date, timedelta

import pytest

from tools import seo_pages
from tools.qa import seo_static

N = seo_pages.SITEMAP_CLOSED_DAYS
PAGE = ('<main><p>이미 접수 마감된 공고예요.</p>'
        '<script type="application/ld+json">{"@type": "FAQPage"}</script>'
        '<script type="application/ld+json">{"@type": "BreadcrumbList"}</script></main>')


def _d(n):
    return (date.fromisoformat(seo_pages.TODAY) - timedelta(days=n)).isoformat()


def _rec(winner_days):
    return {"live": False, "closed": True, "units": [{"id": "x-1", "notice": _d(winner_days + 20), "apply": _d(winner_days + 8),
                                                     "apply_end": _d(winner_days + 6), "winner": _d(winner_days)}]}


def _setup(tmp_path, monkeypatch, recs, in_sitemap):
    for nid in recs:
        p = tmp_path / "notice" / nid / "index.html"
        p.parent.mkdir(parents=True)
        p.write_text(PAGE, encoding="utf-8")
    urls = "".join(f"<url><loc>https://cheongyakpass.kr/notice/{n}/</loc><lastmod>2026-11-18</lastmod></url>" for n in in_sitemap)
    (tmp_path / "sitemap.xml").write_text(f"<urlset>{urls}</urlset>", encoding="utf-8")
    monkeypatch.setattr(seo_static, "DOCS", tmp_path)
    monkeypatch.setattr(seo_pages, "feature", lambda k: True)
    monkeypatch.setattr(seo_pages, "gather", lambda: (recs, {}))


def test_day30_kept_day31_stale_only(tmp_path, monkeypatch):
    recs = OrderedDict([("d30", _rec(N)), ("d31", _rec(N + 1))])
    _setup(tmp_path, monkeypatch, recs, ["d30", "d31"])   # 전날 만든 sitemap: 둘 다 있음
    r = seo_static.run()
    assert r["ok"], r["not_in_sitemap"]
    assert r["not_in_sitemap"] == []
    assert r["sitemap_stale"] == ["notice/d31/"]


def test_day32_still_in_sitemap_fails(tmp_path, monkeypatch):
    recs = OrderedDict([("d32", _rec(N + 2))])
    _setup(tmp_path, monkeypatch, recs, ["d32"])
    r = seo_static.run()
    assert not r["ok"]
    assert r["not_in_sitemap"] == ["notice/d32/ (오래된 마감 공고인데 sitemap 에 있음)"]


def test_missing_page_still_fails(tmp_path, monkeypatch):
    recs = OrderedDict([("d30", _rec(N)), ("d31", _rec(N + 1))])
    _setup(tmp_path, monkeypatch, recs, ["d31"])           # 30일째(실어야 함)가 빠짐
    r = seo_static.run()
    assert not r["ok"]
    assert r["not_in_sitemap"] == ["notice/d30/"]
    assert r["sitemap_stale"] == ["notice/d31/"]


def test_day31_already_removed_is_fine(tmp_path, monkeypatch):
    recs = OrderedDict([("d31", _rec(N + 1))])
    _setup(tmp_path, monkeypatch, recs, [])                # 오늘 만든 sitemap: 31일째는 이미 빠짐
    r = seo_static.run()
    assert r["ok"] and r["sitemap_stale"] == [] and r["not_in_sitemap"] == []


def test_gather_failure_warns(tmp_path, monkeypatch):
    recs = OrderedDict([("d30", _rec(N))])
    _setup(tmp_path, monkeypatch, recs, ["d30"])

    def boom():
        raise ModuleNotFoundError("No module named 'httpx'")
    monkeypatch.setattr(seo_pages, "gather", boom)
    r = seo_static.run()
    assert r["warnings"] and "계산하지 못함" in r["warnings"][0]
