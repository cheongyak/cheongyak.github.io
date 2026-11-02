"""2026-11-03 아침 자동 고치기 — 공주시(덕성그린시티빌,신한1차) 국민임대 자격완화 공고(2015122300020962, 원문 evidence/lh/2015122300020962.txt).
새 꼴: 기준 표 칸에 금액 대신 '배제'만 적음 — '■ 소득 및 자산보유 기준(금회공고 한) 구분 소득 및 자산보유 기준 소득 배제 자산 총자산가액 배제
자동차가액 세대구성원 전원이 보유하고 있는 개별 자동차가액 ( 4,542 )만원 이하' (pdfplumber 는 '소득 배제 총자산가액 배제 자산' 순서)."""
from pathlib import Path

from app.lh_terms import parse_lh_terms

ROOT = Path(__file__).resolve().parents[1]
GONGJU = "2015122300020962"
NAME = "공주시(덕성그린시티빌,신한1차) 국민임대 자격완화 입주자 모집공고(26.11.02)"


def _texts(i):
    out = {"pypdf": (ROOT / "evidence/lh" / f"{i}.txt").read_text(encoding="utf-8")}
    for k in ("pdfium", "plumber"):
        p = ROOT / "evidence/lh" / k / f"{i}.txt"
        if p.exists():
            out[k] = p.read_text(encoding="utf-8")
    return out


def test_gongju_income_asset_excluded_all_tools():
    for tool, t in _texts(GONGJU).items():
        g = parse_lh_terms(t, "국민임대", NAME, None)["groups"][0]
        assert (g["key"], g["income_pct"], g["asset_manwon"], g["car_manwon"]) == ("일반", "excluded", "excluded", 4542), tool


def test_quote_is_original_table():
    q = parse_lh_terms(_texts(GONGJU)["pypdf"], "국민임대", NAME, None)["quotes"]["일반"]
    assert "구분 소득 및 자산보유 기준 소득 배제 자산 총자산가액 배제" in q["income"]
    assert "총자산가액 배제" in q["asset"]


def _one(body):
    t = "4. 신청자격 입주자모집공고일 현재 무주택세대구성원 ■ 소득 및 자산보유 기준(금회공고 한) " + body + " ■ 소득․자산 산정방법 끝"
    return parse_lh_terms(t, "국민임대", "시험 국민임대 예비입주자 모집", None)["groups"][0]


def test_rule_needs_header_and_both_excluded():
    """표 머리 바로 뒤에 소득·총자산 '배제'가 둘 다 있을 때만 — 하나만 '배제'거나 머리가 없으면 읽지 않는다(None → 화면 '공고문 확인')"""
    g = _one("구분 소득 및 자산보유 기준 소득 배제 자산 총자산가액 배제 자동차가액 개별 자동차가액 ( 4,542 )만원 이하")
    assert (g["income_pct"], g["asset_manwon"], g["car_manwon"]) == ("excluded", "excluded", 4542)
    g = _one("구분 소득 및 자산보유 기준 소득 배제 총자산가액 배제 자산 자동차가액 개별 자동차가액 ( 4,542 )만원 이하")   # pdfplumber 순서
    assert (g["income_pct"], g["asset_manwon"]) == ("excluded", "excluded")
    g = _one("구분 소득 및 자산보유 기준 소득 배제 자산 총자산가액 합산기준 ( 345 )백만원 이하")       # 총자산은 금액 → 기존 규칙
    assert g["income_pct"] is None and g["asset_manwon"] == 34500
    g = _one("소득 배제 자산 총자산가액 배제")                                                          # 표 머리 없음
    assert g["income_pct"] is None and g["asset_manwon"] is None
