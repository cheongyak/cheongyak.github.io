"""2026-11-27 운영자 요청 (기능 rental_noindex): 광고 심사 '가치 없는 콘텐츠' 방지 —
임대 공고 중 계층별 소득·자산 기준을 읽지 못했고 AI 참고 내용도 없어 본문이 얇은 페이지는 <meta name="robots" content="noindex, follow"> 를 넣고 sitemap 에서 뺀다."""
import pytest

from tools import seo_pages as S
from tools.qa import seo_static


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(S, "feature", lambda k: True)


RENT = {"id": "T1", "name": "시험 행복주택 입주자 모집", "type": "행복주택", "region": "경기도", "posted": "2099-01-02", "close": "2099-01-20", "url": "https://example.org/n"}


def test_thin_rental_page_is_noindex_and_page_with_terms_is_not(on, monkeypatch):
    assert S.NOINDEX == '<meta name="robots" content="noindex, follow">'
    assert S.NOINDEX in S.rental_page("lh", dict(RENT))[3]
    full = dict(RENT, terms={"groups": [{"key": "청년", "name": "청년", "homeless": "self", "income_pct": {"1": 120, "2": 110, "3+": 100}, "asset_manwon": 25100, "car_manwon": 4542}]})
    assert S.NOINDEX not in S.rental_page("lh", full)[3]
    monkeypatch.setattr(S, "feature", lambda k: k != "rental_noindex")
    assert S.NOINDEX not in S.rental_page("lh", dict(RENT))[3]             # 스위치 끔


def test_checker_fails_when_noindex_page_is_in_sitemap(tmp_path, monkeypatch):
    for slug, extra in (("rental/lh/a/", S.NOINDEX), ("rental/lh/b/", "")):
        p = tmp_path / slug / "index.html"
        p.parent.mkdir(parents=True)
        p.write_text(f"<head>{extra}</head><main><p>임대 공고</p></main>", encoding="utf-8")
    monkeypatch.setattr(seo_static, "DOCS", tmp_path)
    monkeypatch.setattr(S, "gather", lambda: (S.OrderedDict(), {}))
    sm = lambda slugs: (tmp_path / "sitemap.xml").write_text("<urlset>" + "".join(f"<url><loc>https://cheongyakpass.kr/{s}</loc><lastmod>2099-01-01</lastmod></url>" for s in slugs) + "</urlset>", encoding="utf-8")
    sm(["rental/lh/b/"])
    r = seo_static.run()
    assert r["not_in_sitemap"] == [] and r["noindex"] == 1                # 색인 제외 페이지는 sitemap 에 없어도 됨
    sm(["rental/lh/a/", "rental/lh/b/"])
    assert seo_static.run()["not_in_sitemap"] == ["rental/lh/a/ (noindex 인데 sitemap 에 있음)"]
