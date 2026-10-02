"""데이터 불변식 검사가 일부러 망가뜨린 데이터를 잡는지 (MASTER QA 26항 '의도적으로 이상한 데이터')."""
from tools.qa.invariants import check

OK = {"id": "N1-084A", "category": "general", "supply_type": "APT", "kind": "일반분양", "price": 5.0, "area": 84.0, "households": 10,
      "special_units": {"newlywed": 2, "first": 1, "total": 3}, "notice": "2026-09-01", "apply": "2026-09-10", "apply_end": "2026-09-11",
      "winner": "2026-09-20", "sido": "서울"}
TODAY = "2026-09-25"


def v(**kw):
    return set(check([{**OK, **kw}], TODAY, True)["violations"])


def test_clean_row_passes():
    assert v() == set()


def test_corrupted_rows_are_caught():
    assert "세대수 음수" in v(households=-1)
    assert "금액 범위 (억)" in v(price=0) and "금액 범위 (억)" in v(price=None)
    assert "전용면적" in v(area=0)
    assert "시·도 없음" in v(sido=None)
    assert "공급 구분 값" in v(category="unknown")
    assert "날짜 순서" in v(apply="2026-09-12", apply_end="2026-09-11")
    assert "공급유형 ↔ 구분 상호배타" in v(supply_type="무순위")                       # 일반분양인데 무순위
    assert "공급유형 ↔ 구분 상호배타" in v(category="remainder", supply_type="APT")
    assert "무순위인데 국민/민영 값" in v(category="remainder", supply_type="불법행위 재공급", house_dtl="국민")
    assert "특공 유형별 합 ≠ 합계" in v(special_units={"newlywed": 2, "total": 3})
    assert "보관 기간 지난 공고가 목록에 남음" in v(winner="2026-09-01", apply="2026-08-20", apply_end="2026-08-21", notice="2026-08-10")
    assert "공공임대인데 일반분양 아님·시세 있음" in v(rental=True, mkt_low=6.0)
    assert check([OK, OK], TODAY, True)["violations"]["ID 중복"]["count"] == 1


def test_expected_town_total_only_is_not_a_violation():
    """신혼희망타운은 청약홈이 특공 유형별 세대 없이 합계만 준다 (2026820010) — 예상된 차이."""
    assert v(supply_type="신혼희망타운", kind="일반분양 · 신혼희망타운", special_units={"newlywed": 0, "total": 78}) == set()
