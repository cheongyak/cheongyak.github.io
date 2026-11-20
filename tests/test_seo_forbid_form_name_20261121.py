"""2026-11-21: LH 공고 첨부 서식 이름 '[양식1-1]입주추천신청서.hwpx'(rental/lh/2015122300021121)가 금지어 '추천'으로 걸려
test_generated_pages_pass_checks 가 실패. 서식 이름은 이 서비스의 권유가 아니라 빼고, 권유하는 '추천'은 그대로 잡는다."""
from tools.qa.seo_static import FORBID


def test_form_name_not_forbidden():
    assert not FORBID.search("[양식1-1]입주추천신청서.hwpx")
    assert not FORBID.search("기관추천 특별공급") and not FORBID.search("등급: 비추천")


def test_recommend_still_forbidden():
    assert FORBID.search("이 공고를 추천해요")
    assert FORBID.search("무조건 넣으세요")
