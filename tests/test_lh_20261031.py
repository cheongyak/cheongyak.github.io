"""LH 임대 공고 4건 '데이터 확인 필요' 정리 (2026-10-31, 공고문 원문 기준). 정답은 tests/golden/lh_rental.json.
- 포항블루밸리 행복주택 963: 완화 공고의 '자동차가액이 아래의 금액 이하일 것' 계층별 표 → 자동차 4,542만원, 무주택 완화('해당지역에 주택이 없을 경우 허용'),
  신혼부부 '입주 전까지 주택청약종합저 축'(PDF 줄바꿈) 가입 증명
- 담양삼만 일자리연계형 905: '■ 신분요건 (※ 다음 ❶∼❹ …)' 계층 + '■ 직업요건 사업·근로소득자' 안내
- 평창장평 일반형 992: 일반공급 '■ 세부 신청자격 청년 … 고령자 … 일반' 머리(번호 없음)
- 평창장평 고령자복지형 993: 고령자복지주택 한 계층"""
import json
from pathlib import Path

from app.lh_terms import parse_lh_terms

ROOT = Path(__file__).resolve().parents[1]


def _p(i, kind):
    return parse_lh_terms((ROOT / "evidence/lh" / f"{i}.txt").read_text(encoding="utf-8", errors="replace"), kind)


def _g(r):
    return {g["key"]: g for g in r["groups"]}


def test_pohang_relaxed_car_table_and_homeless():
    r = _p("2015122300020963", "행복주택")
    G = _g(r)
    assert r["relaxed"] and r["homeless_relaxed"]
    assert set(G) == {"청년", "신혼부부·한부모", "고령자"}
    assert all(g["income_pct"] == "excluded" and g["asset_manwon"] == "excluded" and g["car_manwon"] == 4542 for g in G.values())
    assert G["청년"]["homeless"] == "self" and G["신혼부부·한부모"].get("account_by_movein") and not G["고령자"].get("account_by_movein")


def test_car_table_needs_birth_bonus_column():
    """출생자녀 1인 칸이 0인 칸 × 1.1 이 아니면(다른 표) 자동차 값을 읽지 않는다"""
    t = (ROOT / "evidence/lh/2015122300020963.txt").read_text(encoding="utf-8", errors="replace").replace("49,960,000원", "47,000,000원")
    G = _g(parse_lh_terms(t, "행복주택"))
    assert all(g["car_manwon"] is None for g in G.values())   # 못 읽으면 화면이 '공고문 확인'으로 보여준다


def test_damyang_job_linked_groups():
    G = _g(_p("2015122300020905", "통합공공임대"))
    assert set(G) == {"청년", "신혼부부·한부모", "장기종사자"}
    for g in G.values():
        assert g["income_pct"] == {"1": 170, "2": 160, "3+": 150} and g["asset_manwon"] == 34500 and g["car_manwon"] == 4542
        assert any("직업요건" in n for n in g.get("notes") or [])
    assert G["신혼부부·한부모"]["dual_add"] == 30 and G["청년"]["homeless"] == "self"


def test_pyeongchang_general_and_elderly():
    G = _g(_p("2015122300020992", "통합공공임대"))
    assert set(G) == {"청년", "신혼부부·한부모", "고령자", "일반"}
    assert G["신혼부부·한부모"]["income_pct"] == {"1": None, "2": 160, "3+": 150} and G["신혼부부·한부모"]["dual_add"] == 30
    assert G["고령자"]["homeless"] == "household_or_single_self"
    E = _g(_p("2015122300020993", "통합공공임대"))
    assert set(E) == {"고령자"} and E["고령자"]["income_pct"] == {"1": 170, "2": 160, "3+": 150} and E["고령자"]["asset_manwon"] == 34500


def test_homeless_relaxed_only_where_notice_says():
    """'해당지역에 주택이 없' 표현을 무주택 완화로 읽는 것은 지금 저장된 원문 중 963 하나뿐이어야 한다(다른 공고 판정이 바뀌지 않게)"""
    import re
    hit = [f.stem for f in sorted((ROOT / "evidence/lh").glob("*.txt"))
           if re.search(r"해당\s?지역에\s?주택(?:이|을)?\s?(?:없|소유하지)", re.sub(r"\s+", " ", f.read_text(encoding="utf-8", errors="replace")))]
    assert hit == ["2015122300020963"], hit
