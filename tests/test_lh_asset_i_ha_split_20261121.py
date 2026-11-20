"""행복주택 계층 총자산 '34,500만원 이 ⏎ 하이고' — PDF 줄바꿈이 '이하'를 가른 꼴 (인천 남동구 행복 자격완화 2015122300021099, 2026-11-21 아침 자동 고치기).
있던 규칙은 '만원 이하'만 읽어 신혼부부·한부모 총자산 칸이 비어 세션이 쓴 답 파일로만 채워지던 것."""
from pathlib import Path

from app.lh_terms import parse_lh_terms

ROOT = Path(__file__).resolve().parents[1]
NAME = "'26년 11월 인천시(남동구) 행복주택 입주자격완화 예비입주자 모집"


def _g(r):
    return {g["key"]: g for g in r["groups"]}


def test_original_21099():
    r = parse_lh_terms((ROOT / "evidence/lh/2015122300021099.txt").read_text(encoding="utf-8"), "행복주택", NAME, "인천광역시")
    G = _g(r)
    assert G["신혼부부·한부모"]["asset_manwon"] == 34500 and G["신혼부부·한부모"]["car_manwon"] == 4542
    assert G["고령자"]["asset_manwon"] == 34500 and G["청년"]["asset_manwon"] == 25100 and G["대학생"]["asset_manwon"] == 10800
    assert "34,500만원 이 하이고" in r["quotes"]["신혼부부·한부모"]["asset"]


def test_no_read_without_ha():
    # '이' 뒤에 '하'가 없으면(이상·이내 등) 상한으로 읽지 않는다
    t = ("3-3. 신혼부부·한부모가족 계층 ④ 해당 세대가 보유하고 있는 총 자산가액 합산기준 34,500만원 이상인 자 "
         "3-4. 고령자 계층 ")
    G = _g(parse_lh_terms(t, "행복주택", "", "인천광역시"))
    assert G.get("신혼부부·한부모", {}).get("asset_manwon") != 34500
