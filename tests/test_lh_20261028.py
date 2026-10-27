"""2026-10-28 아침 자동 고치기 — 화성 동탄 행복주택 입주자격 완화 공고(2015122300020958, 원문 evidence/lh/2015122300020958.txt).
새 꼴: 계층 절 '④ 【완화조건】 자산요건 배제하되, 해당 세대의 총 자산 중 자동차가액이 4,542만원이하일 것'(청년·신혼부부·고령자)
· '④ 【완화조건】 자산요건 배제(단, 신청자 본인이 자동차가액 산출대상 자동차를 소유하고 있지 않을 것)'(대학생) — '총' 없이 '자산요건'만 적음."""
from pathlib import Path

from app.lh_terms import parse_lh_terms

ROOT = Path(__file__).resolve().parents[1]
DONGTAN = "2015122300020958"
NAME = "화성시 동탄지역 행복주택 입주자 모집 공고[입주자격완화/선계약후검증]('26.10.27.)"


def _texts(i):
    out = {"pypdf": (ROOT / "evidence/lh" / f"{i}.txt").read_text(encoding="utf-8")}
    for k in ("pdfium", "plumber"):
        p = ROOT / "evidence/lh" / k / f"{i}.txt"
        if p.exists():
            out[k] = p.read_text(encoding="utf-8")
    return out


def test_dongtan_relaxed_asset_excluded_all_tools():
    """pypdf·pdfium: 대학생·청년·신혼부부·고령자 모두 소득·자산 배제, 자동차 대학생 0(소유 불가)·나머지 4,542만원.
    pdfplumber 는 청년 절 글 순서가 섞여 청년을 못 읽지만(None — 세 도구 합치기가 다른 도구 값으로 채움) 틀린 값은 내지 않는다."""
    want = {"대학생": ("excluded", "excluded", 0), "청년": ("excluded", "excluded", 4542),
            "신혼부부·한부모": ("excluded", "excluded", 4542), "고령자": ("excluded", "excluded", 4542)}
    for tool, t in _texts(DONGTAN).items():
        P = {g["key"]: g for g in parse_lh_terms(t, "행복주택", NAME, "경기도")["groups"]}
        for k, v in want.items():
            got = (P[k]["income_pct"], P[k]["asset_manwon"], P[k]["car_manwon"])
            assert got == v or (tool == "plumber" and k == "청년" and got == (None, None, None)), (tool, k, got)


def test_asset_excluded_quote_is_original_sentence():
    r = parse_lh_terms(_texts(DONGTAN)["pypdf"], "행복주택", NAME, "경기도")
    assert r["quotes"]["청년"]["asset"] == "【완화조건】 자산요건 배제하되, 해당 세대의 총 자산 중 자동차가액이 4,542만원이하일 것"
    assert r["quotes"]["대학생"]["asset"] == "【완화조건】 자산요건 배제(단, 신청자 본인이 자동차가액 산출대상 자동차를 소유하고 있지 않을 것)"


def _one(body):
    t = ("1. 개요 입주자격 완화 3-1. 대학생 계층 ■ 공급대상자 무주택자 ① 대학 재학 ② 혼인 중이 아닐 것 "
         "3-2. 청년 계층 ■ 공급대상자 무주택자 ① 19세 이상 39세 이하 ② 혼인 중이 아닐 것 ③ 【완화조건】 소득요건 배제 " + body + " 3-3. 끝")
    return {g["key"]: g for g in parse_lh_terms(t, "행복주택", "시험[입주자격완화]", "경기도")["groups"]}["청년"]


def test_rule_needs_relax_mark_and_proviso():
    """【완화조건】 표시와 단서('하되,' 또는 '(단,')가 함께 있을 때만 배제 — 하나라도 없으면 자산 기준을 읽지 않는다(None → 화면 '공고문 확인')"""
    assert _one("④ 【완화조건】 자산요건 배제하되, 해당 세대의 총 자산 중 자동차가액이 4,542만원이하일 것")["asset_manwon"] == "excluded"
    assert _one("④ 자산요건 배제하되, 해당 세대의 총 자산 중 자동차가액이 4,542만원이하일 것")["asset_manwon"] is None    # 완화 표시 없음
    assert _one("④ 【완화조건】 자산요건 배제 여부는 별도 안내")["asset_manwon"] is None                                    # 단서 없음
    assert _one("④ 【완화조건】 자산요건 배제하되, 해당 세대의 총 자산 중 자동차가액이 4,542만원이하일 것")["car_manwon"] == 4542
