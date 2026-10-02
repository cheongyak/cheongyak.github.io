"""공급 세대 0 주택형 빼기 (기능: gen_none). 근거: 2026000414 인천계양 A6 공고문 공급표 — 59C 총 15세대 중 사전청약 당첨자 15 → 이번 공급 0"""
from app.pipeline import no_supply


def raw(**kw):
    r = {"category": "general", "name": "인천계양지구 A6블록 공공분양주택(본청약)", "households": 0,
         "special_units": {"newborn": 0, "newlywed": 0, "first": 0, "multichild": 0, "elder": 0, "total": 0}}
    r.update(kw)
    return r


def test_zero_general_and_zero_special_is_dropped():
    assert no_supply(raw())


def test_special_only_type_is_kept():   # 59G: 일반 0, 특별공급 6
    assert not no_supply(raw(special_units={"newborn": 1, "newlywed": 1, "first": 1, "multichild": 1, "total": 6}))


def test_one_general_unit_is_kept():   # 59H: 일반 1
    assert not no_supply(raw(households=1))


def test_remainder_without_special_counts_is_kept():   # 과천 라비엔오 84D 재공급: 특별공급 세대수를 청약홈이 안 줌
    assert not no_supply(raw(category="remainder", special_units=None))


def test_unknown_households_is_kept():   # 세대수를 못 받았으면(None) 빼지 않는다
    assert not no_supply(raw(households=None))
