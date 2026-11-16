"""애드센스 미승인 대응 (2026-11-16 운영자): 첫 화면 초기 HTML 보강(기능 seo_home)·sitemap 범위(기능 sitemap_recent)·광고 허용 화면.

① seo_home 을 끄면 첫 화면 미리 그린 글이 예전과 같고, 켜면 서비스 설명·가이드 링크·소개/정책 링크가 들어간다 (금지 표현 없음)
② sitemap_recent: 접수 예정·접수 중·최근 마감(30일)만 sitemap 에, 끄면 전부
③ 화면 코드: 광고 자리는 허용 화면(AD_VIEWS = 목록·상세)에서만 — 내 조건·알림·가점 컷이 허용 목록에 없다
"""
import re
from collections import OrderedDict
from datetime import date, timedelta

from tools import seo_pages


def _recs():
    d = lambda n: (date.fromisoformat(seo_pages.TODAY) - timedelta(days=n)).isoformat()
    mk = lambda closed, **L: {"live": not closed, "closed": closed, "type": "민영", "eng": {}, "res": {}, "units": [dict({"id": "x-1", "name": "시험 단지", "sido": "서울"}, **L)]}
    return OrderedDict([
        ("open", mk(False, notice=d(3), apply=d(-5), apply_end=d(-7))),
        ("recent", mk(True, notice=d(40), apply=d(20), apply_end=d(18), winner=d(10))),          # 당첨자 발표 10일 전 → 싣는다
        ("edge", mk(True, notice=d(80), apply=d(60), apply_end=d(58), winner=d(seo_pages.SITEMAP_CLOSED_DAYS))),   # 딱 30일 → 싣는다
        ("old", mk(True, notice=d(120), apply=d(100), apply_end=d(98), winner=d(seo_pages.SITEMAP_CLOSED_DAYS + 1))),   # 31일 → 뺀다
        ("old_nowinner", mk(True, notice=d(200), apply=d(190), apply_end=d(188))),
    ])


def test_sitemap_recent_keeps_open_and_recently_closed(monkeypatch):
    monkeypatch.setattr(seo_pages, "feature", lambda k: True)
    assert seo_pages.sitemap_skip(_recs()) == {"notice/old/", "notice/old_nowinner/"}
    monkeypatch.setattr(seo_pages, "feature", lambda k: k != "sitemap_recent")
    assert seo_pages.sitemap_skip(_recs()) == set()                                              # 스위치를 끄면 전부 싣는다


def test_seo_home_adds_description_and_guide_links(monkeypatch):
    eng = {"rules": {"lottoAbs": 5, "lottoRate": 0.3, "considerAbs": 1}, "names": {"lotto": "로또", "consider": "고려", "flat": "마진없음", "pass": "비추천", "unknown": "시세 부족"}}
    recs = OrderedDict(list(_recs().items())[:2])
    monkeypatch.setattr(seo_pages, "feature", lambda k: k != "seo_home")
    off = seo_pages.prerender_block(recs, eng)
    assert seo_pages.home_extra(eng) == "" and "청약패스로 할 수 있는 일" not in off and "/terms/" not in off
    monkeypatch.setattr(seo_pages, "feature", lambda k: True)
    on = seo_pages.prerender_block(recs, eng)
    assert on.replace(seo_pages.home_extra(eng), "").replace(seo_pages.HOME_FOOT, "") == off      # 더한 것 말고는 예전과 글자 하나 다르지 않다
    for href in ("/guide/score-calc/", "/guide/account-first-rank/", "/guide/special-overview/", "/guide/", "/story/", "/about/", "/privacy/", "/terms/"):
        assert f'<a href="{href}">' in on, href
    for h in ("청약패스로 할 수 있는 일", "등급은 이렇게 정해요", "데이터와 검증", "청약 가이드"):
        assert h in on
    assert not seo_pages.check_text(on)                                                           # 금지 표현(권유·단정) 없음
    assert len(re.sub(r"<[^>]+>", "", on)) > 2500                                                 # 3줄 요약이 아니라 읽을 글이 있다
    for g in re.findall(r'href="/guide/([a-z0-9-]+)/"', on):
        assert (seo_pages.GUIDES / f"{g}.json").exists() or g in ("score", "deposit"), g           # 없는 가이드로 걸지 않는다


def test_ad_views_exclude_form_and_empty_screens():
    s = (seo_pages.DOCS / "index.html").read_text(encoding="utf-8")
    views = re.search(r"const AD_VIEWS = \[([^\]]*)\]", s).group(1)
    assert sorted(re.findall(r"'(\w+)'", views)) == ["detail", "feed"]                            # 내 조건(me)·알림(alerts)·가점 컷(trend)은 없다
    assert "if (!adsOn() || !AD_VIEWS.includes(S.view)) return '';" in s
    assert "if (AD_VIEWS.includes(S.view)) adsAfterRender(); else adsStrip();" in s
