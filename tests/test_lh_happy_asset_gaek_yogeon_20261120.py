"""행복주택 완화 공고 '총자산가액 요건은 배제하나' — '가액 요건' 두 낱말 (수원당수 1, 2단지 행복 자격완화 2015122300021108, 2026-11-20 아침 자동 고치기).
있던 규칙은 '총자산가액 배제'·'총 자산요건 배제'만 읽어, 청년·대학생 총자산 칸이 비어 세션이 쓴 답 파일로만 채워지던 것."""
from pathlib import Path

from app.lh_terms import parse_lh_terms

ROOT = Path(__file__).resolve().parents[1]
NAME = "수원당수 1, 2단지 행복주택 입주자격완화 동호지정 입주자 모집[선계약/후검증]('26.11.18.)"


def _g(r):
    return {g["key"]: g for g in r["groups"]}


def test_original_21108():
    r = parse_lh_terms((ROOT / "evidence/lh/2015122300021108.txt").read_text(encoding="utf-8"), "행복주택", NAME, "경기도")
    G = _g(r)
    assert G["청년"]["asset_manwon"] == "excluded" and G["청년"]["car_manwon"] == 4542
    assert G["대학생"]["asset_manwon"] == "excluded" and G["대학생"]["car_manwon"] == 0
    assert "총자산가액 요건은 배제하나" in r["quotes"]["청년"]["asset"]


def test_not_excluded_without_baeje():
    # '총자산가액 요건' 뒤에 '배제'가 없으면 배제로 읽지 않는다
    t = ("4-2. 청년 계층 ③ 해당 세대의 소득요건 배제 ④ 해당 세대의 총자산가액 요건은 충족하여야 하며 총 자산 중 자동차가액이 4,542만원 이하일 것 "
         "4-3. 주거급여수급자 ")
    G = _g(parse_lh_terms(t, "행복주택", "", "경기도"))
    assert G["청년"]["asset_manwon"] != "excluded"
