"""기능 seo_content (2026-11-04 애드센스·애드핏 재심사) — 검색용 정적 페이지 시험.

① 공고 페이지: 산문(표 제외) 1,500자 이상, FAQ 5개·FAQPage·BreadcrumbList 구조화 데이터, 금지어 없음, 등급·판정 이유는 화면 엔진 값 그대로
② 스위치가 꺼져 있으면 정적 페이지 틀이 예전과 같다('베타' 띠 그대로), 켜지면 '베타'를 빼고 참고용 안내는 남긴다
③ 금지어 검사는 제도·등급 이름(기관추천·비추천)을 잡지 않는다
④ 지금 docs 에 새 페이지가 있으면(스위치 켜짐) 전체 검사(tools.qa.seo_static) 통과
고정본: tests/qa/seo_fixture.json (2026000528 광교 자연앤 센트레빌 + 화면 엔진 결과)
"""
import json
import re
from collections import OrderedDict
from pathlib import Path

import pytest

from tools import build_static, seo_pages
from tools.qa import seo_static

FX = json.loads((Path(__file__).parent / "qa" / "seo_fixture.json").read_text(encoding="utf-8"))


def rec(closed=False):
    return {"live": True, "units": FX["units"], "eng": FX["eng"], "res": {}, "recap": None, "closed": closed, "type": seo_pages.ntype(FX["units"][0])}


def test_notice_page_prose_faq_ld():
    r = rec()
    recs = OrderedDict([("2026000528", r)])
    eng = {"rules": FX["rules"], "names": FX["names"]}
    t, d, body, head, crumbs = seo_pages.notice_page("2026000528", r, recs, eng)
    html = f"<main>{body}</main>"
    text = seo_static.prose(html)
    assert len(text) >= 1500, len(text)
    assert not seo_pages.check_text(body)
    assert body.count("<dt>") == 5                      # 자주 묻는 질문 5개
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', head).group(1))
    assert ld["@type"] == "FAQPage" and len(ld["mainEntity"]) == 5
    assert [c[1] for c in crumbs][:3] == ["홈", "청약 공고", "경기도"] and crumbs[3][1] == "공공분양"
    # 등급·마진 문구는 화면 엔진 결과(seo_engine)를 그대로 쓴다 — 새로 계산하지 않는다
    assert sum(x["margin"] in body for x in FX["eng"].values()) >= 2   # 예시 주택형 2개의 마진 문구 = 화면 marginText
    labels = [x["label"] for x in FX["eng"].values()]
    assert f"'{labels[0]}' {labels.count(labels[0])}개" in body
    assert "세전 추정이고 확정 수익이 아니에요" in body
    # 공고 조건(규제지역 1순위 세대주)은 화면 판정과 같은 뜻으로
    assert "규제지역이라 일반공급 1순위는 공고일 기준 세대주만" in body


def test_closed_notice_result_section():
    r = rec(closed=True)
    r["res"] = {"units": {"084.7637A": {"unit": "84A", "supply": 30, "req": 900, "rate": "30.00", "rate_num": 30.0, "low": 61, "avg": 66}}}
    recs = OrderedDict([("2026000528", r)])
    t, d, body, head, crumbs = seo_pages.notice_page("2026000528", r, recs, {"rules": FX["rules"], "names": FX["names"]})
    assert "청약 결과와 판정 복기" in body and "30.00대 1" in body and "61점" in body
    assert "결과" in t


def test_forbidden_words():
    assert seo_pages.check_text("기관추천 특별공급과 '비추천' 등급") == []
    assert seo_pages.check_text("이 공고를 추천해요") == ["추천"]
    assert seo_pages.check_text("무조건 넣으세요") == ["무조건"]
    assert seo_static.FORBID.search("당첨 가능성 높아요")


def test_korean_particles():
    assert seo_pages.ieyo("17일") == "이에요" and seo_pages.ieyo("고려") == "예요"
    assert seo_pages.ro("시세 부족") == "으로" and seo_pages.ro("고려") == "로" and seo_pages.ro("마진없음") == "으로"
    assert seo_pages.man(9.489) == "9억 4,890만 원" and seo_pages.man(0.9489) == "9,489만 원"


def test_page_template_switch(monkeypatch):
    monkeypatch.setattr(build_static, "seo_on", lambda: False)
    off = build_static.page("x/", "제목", "설명", "<p>본문</p>")
    assert '<span class="beta">베타</span>' in off and "<b>베타 · 참고용</b>" in off and "application/ld+json" not in off
    monkeypatch.setattr(build_static, "seo_on", lambda: True)
    on = build_static.page("x/", "제목", "설명", "<p>본문</p>", "", [("/", "홈"), (None, "제목")])
    assert "베타" not in on and "<b>참고용</b>" in on and "모집공고문" in on
    assert "BreadcrumbList" in on and 'href="/about/operator/"' in on and 'href="/about/policy/"' in on and 'href="/about/sources/"' in on


def test_prerender_block_markers(tmp_path, monkeypatch):
    idx = tmp_path / "index.html"
    idx.write_text('<body><div id="app" class="shell" aria-live="polite"></div></body>', encoding="utf-8")
    monkeypatch.setattr(seo_pages, "DOCS", tmp_path)
    seo_pages.set_prerender(seo_pages.MARK_A + "<p>오늘 공고</p>" + seo_pages.MARK_B)
    assert "오늘 공고" in idx.read_text(encoding="utf-8")
    seo_pages.set_prerender("")   # 꺼지면 원래대로
    assert idx.read_text(encoding="utf-8") == '<body><div id="app" class="shell" aria-live="polite"></div></body>'


@pytest.mark.skipif(not (seo_static.DOCS / "rental").exists(), reason="seo_content 가 꺼져 있어 새 페이지가 없음")
def test_generated_pages_pass_checks():
    r = seo_static.run()
    assert r["ok"], {k: r[k][:5] for k in ("short", "forbidden", "broken", "ld_bad", "ld_missing", "not_in_sitemap")}


def test_closed_notice_without_results_title_matches_content():
    """2026-11-05 애드센스 지적: 결과를 모으지 못한 마감 공고가 '청약 결과·경쟁률·당첨 가점' 제목으로 나가던 것 — 제목·요약·FAQ 가 실제 내용과 같게"""
    r = rec(closed=True)
    recs = OrderedDict([("2026000528", r)])
    t, d, body, head, crumbs = seo_pages.notice_page("2026000528", r, recs, {"rules": FX["rules"], "names": FX["names"]})
    assert "결과·경쟁률" not in t and "공고 정리" in t and "접수 마감" in t
    assert "청약 결과와 판정 복기" not in body and "결과를 모으지 못해" in body
    assert "경쟁률과 당첨 가점은 어땠어요" not in body and "청약 결과는 어디서 볼 수 있어요" in body
    assert re.findall(r'<span class="secno">(\d+)</span>', body)[:3] == ["01", "02", "03"]   # 빠진 단원 때문에 번호가 건너뛰지 않음
    # 경쟁률만 있고 가점이 없으면 제목·표에 가점을 넣지 않는다
    r["res"] = {"units": {"084.7637A": {"unit": "84A", "supply": 30, "req": 12, "rate": "(△18)", "rate_num": 0.4, "low": 0, "avg": 0}}}
    t, d, body, head, crumbs = seo_pages.notice_page("2026000528", r, recs, {"rules": FX["rules"], "names": FX["names"]})
    assert "결과·경쟁률" in t and "당첨 가점" not in t and "<th>당첨 최저 가점</th>" not in body


def test_rental_schedule_and_title():
    """LH 접수 시각 칸이 '~' 만 오면 날짜 칸을 쓴다(홍성군 영구임대 2015122300020903), 제목에 접수 기간(같은 이름 공고 SH-311375·311987 구분)"""
    sch = {"apply_start": "2026-11-02", "apply_end": "2026-11-05", "apply_time": "~", "winner": "2027-01-27"}
    assert seo_pages.rent_apply(sch) == "2026.11.02 ~ 2026.11.05"
    assert seo_pages.rent_apply({"apply_time": "2026.11.09 10:00 ~ 2026.11.11 16:10"}) == "2026.11.09 10:00 ~ 2026.11.11 16:10"
    assert seo_pages.rent_apply({"apply_time": "~"}) == ""
    n = {"id": "2015122300020903", "name": "홍성군 영구임대 예비자 모집공고", "type": "영구임대", "region": "충청남도", "posted": "2026-10-19", "close": "2026-11-05", "schedule": [sch]}
    t, d, body, head, crumbs = seo_pages.rental_page("lh", n)
    assert "접수는 ~이고" not in body and "접수는 2026.11.02 ~ 2026.11.05" in head and "(접수 2026.11.02~11.05)" in t
    n2 = dict(n, schedule=[{"apply_time": "~"}])
    t2, d2, body2, head2, _ = seo_pages.rental_page("lh", n2)
    assert "접수는 ~" not in head2 and "모집공고문에서 확인" in head2 and "(게시 2026.10.19)" in t2


def test_operator_name_from_privacy():
    frag = "<h3>9. 개인정보 보호책임자</h3><table><tr><th>책임자</th><td>차진혁</td></tr><tr><th>연락처</th><td>x@example.com</td></tr></table>"
    assert seo_pages.operator_name(frag) == "차진혁"
    assert seo_pages.operator_name("<p>보호책임자 책임자 연락처</p>") == ""
