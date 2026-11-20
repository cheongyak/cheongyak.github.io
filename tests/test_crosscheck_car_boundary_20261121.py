"""공고문 대조 자동차 기준 — 요약 표 한 줄 '(부동산,자동차) 해당 없음 (세대) 부동산 215,500천원 이하 자동차 45,420천원 이하' 에서
부동산 금액의 뒤 다섯 자리 '15,500'을 자동차 기준으로 잘라 읽어 거짓 '공고문 대조' 경고 (고창 데시앙 2·3블록 공공분양 2026000598·597, 2026-11-21 아침 자동 고치기)."""
from pathlib import Path

from app.crosscheck import app_constants, notice_problems
from app.notice_pdf import notice_facts

ROOT = Path(__file__).resolve().parents[1]


def test_gochang_originals_no_false_car():
    for no in ("2026000597", "2026000598"):
        t = (ROOT / f"evidence/notices/{no}.txt").read_text(encoding="utf-8")
        assert "(세대) 부동산 215,500천원 이하 자동차 45,420천원 이하" in t
        a = notice_facts(t)["asset_thousand"]
        assert a["자동차"] == [45420, 49960, 54510], (no, a["자동차"])
        assert notice_problems({"asset_thousand": a}, app_constants()) == [], no


def test_real_car_difference_still_flagged():
    a = notice_facts("(부동산,자동차) 해당 없음 (세대) 부동산 215,500천원 이하 자동차 35,000천원 이하")["asset_thousand"]
    assert a["자동차"] == [35000]
    assert any("35,000" in x for x in notice_problems({"asset_thousand": a}, app_constants()))
