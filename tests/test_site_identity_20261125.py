"""2026-11-25 운영자: 네이버 검색·AI 브리핑이 청약패스를 공식 출처로 알아보게 (기능 site_identity)
- 사이트 연관 채널 JSON-LD(Organization·WebSite: name·url·sameAs·description)를 메인과 주요 정적 페이지 <head> 에
- /about/ 의 '데이터 검증 현황' 위에 '청약패스 소개'(요약·주요 기능 3·출처와 갱신·자주 묻는 질문)
- 스위치를 끄면 정적 페이지는 예전과 같다(메인 index.html 의 <head> 는 손으로 넣은 것이라 되돌리려면 커밋을 되돌린다)."""
import json
import re

from tools import build_static as B
from tools.qa.seo_static import FORBID

FRAG = ('<p class="small muted">판정은 참고용이에요.</p><section class="card"><div class="row"><h2>데이터 검증 현황</h2></div><dl class="kv"></dl></section><div class="menulist"></div>')


def _lds(doc):
    return [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc[: doc.index("</head>")], re.S)]


def test_jsonld_values_as_operator_gave():
    lds = _lds("<head>" + B.site_jsonld() + "</head>")
    assert [d["@type"] for d in lds] == ["Organization", "WebSite"]
    for d in lds:
        assert d["@context"] == "https://schema.org" and d["name"] == "청약패스" and d["url"] == "https://cheongyakpass.kr"
        assert d["sameAs"] == ["https://blog.naver.com/cheongyakpass"]
        assert d["description"] == "청약홈 모집공고마다 신청 자격(일반·특별공급), 시세 대비 마진, 계약금·중도금·잔금 필요 자금을 계산해 주는 아파트 청약 정리 서비스"


def test_index_head_has_same_jsonld():
    doc = (B.DOCS / "index.html").read_text(encoding="utf-8")
    assert [d for d in _lds(doc) if d["@type"] in ("Organization", "WebSite")] == _lds("<head>" + B.site_jsonld() + "</head>")


def test_main_static_pages_get_jsonld_but_not_leaf_pages(monkeypatch):
    monkeypatch.setattr(B, "feature", lambda k: True)
    types = lambda slug: [d["@type"] for d in _lds(B.seo_page(slug, "제목", "설명", "<h1>제목</h1>", "", [("/", "홈"), (None, "제목")]))]
    for slug in ("about/", "about/operator/", "about/policy/", "about/sources/", "story/", "guide/", "notice/", "rental/"):
        assert types(slug)[:2] == ["Organization", "WebSite"], slug
    for slug in ("notice/2026000001/", "guide/score/", "rental/lh/1/", "terms/", "privacy/"):
        assert "Organization" not in types(slug), slug


def test_about_intro_above_verify_block_and_verify_block_kept(monkeypatch):
    monkeypatch.setattr(B, "feature", lambda k: True)
    body = B.about_body(FRAG)
    assert body.startswith("<h1>이용 안내</h1>") and body.index('id="about-intro"') < body.index("데이터 검증 현황")
    assert body.replace(B.ABOUT_INTRO, "") == "<h1>이용 안내</h1>" + FRAG          # 기존 내용은 글자 하나 안 바뀜
    for must in ("청약패스(cheongyakpass.kr)", "일반·특별공급 자격 판정", "주변 실거래가 대비 시세 마진·등급 비교", "필요 현금 계산", "데이터 출처와 갱신 주기",
                 "청약홈(한국부동산원)", "국토교통부 실거래가", "매일 새벽", "참고용 추정", "모집공고문", "자주 묻는 질문"):
        assert must in B.ABOUT_INTRO, must
    assert 3 <= B.ABOUT_INTRO.count("<dt>Q. ") <= 4 and B.ABOUT_INTRO.count("<dt>") == B.ABOUT_INTRO.count("<dd>A. ")
    assert not FORBID.search(re.sub(r"<[^>]+>", " ", B.ABOUT_INTRO))


def test_about_intro_fallback_when_verify_block_missing(monkeypatch):
    monkeypatch.setattr(B, "feature", lambda k: True)
    body = B.about_body("<p>안내</p>")
    assert body == "<h1>이용 안내</h1>" + B.ABOUT_INTRO + "<p>안내</p>"


def test_switch_off_is_as_before(monkeypatch):
    monkeypatch.setattr(B, "feature", lambda k: k != "site_identity")
    assert B.about_body(FRAG) == "<h1>이용 안내</h1>" + FRAG
    assert "Organization" not in B.seo_page("about/", "이용 안내", "설명", "<h1>이용 안내</h1>", "", [("/", "홈"), (None, "이용 안내")])
