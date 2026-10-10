"""공공분양식 공공임대 특별공급 소득표 (기능 rental_pub_table_sp, 2026-10-10 사용자 'Abc 순차' A).
원문 2026000402 (표3)의 특별공급 칸을 읽되, 금액이 도시근로자 2025 × % 와 1원 단위로 같은 유형만 받는다 (정답: tests/golden/notices.json 2026000402)."""
import re
from pathlib import Path

from app import notice_pdf

ROOT = Path(__file__).resolve().parents[1]
T = re.sub(r"\s+", " ", (ROOT / "evidence/notices/2026000402.txt").read_text(encoding="utf-8"))


def test_reads_consistent_types_only():
    pl = notice_pdf.parse_pub_limits((ROOT / "evidence/notices/2026000402.txt").read_text(encoding="utf-8"))
    assert set(pl["sp"]) == {"multichild", "elder", "first", "newborn"}
    assert pl["sp_unread"] == ["newlywed"]   # 신혼부부 일반·추첨 칸 3인 이상 금액이 다른 해 기준 → 판정하지 않음
    assert "2" not in pl["sp"]["multichild"]["amt"]   # 다자녀 2인 칸은 '-'
    assert pl["sp"]["elder"]["amt"]["2"][0] == [7626151, 8212778] and pl["sp"]["elder"]["pct2"][1] == [130, 200]
    assert pl["sp"]["newborn"]["tiers"] == [["우선공급", 70, 100, 120], ["일반공급", 20, 140, 150], ["추첨공급", 10, 140, 200]]
    assert pl["relax"] == {"real_estate": [23705, 25860], "car": [4996, 5451]}


def test_one_wrong_amount_drops_that_type():
    i = T.find("(표3) 전년도 도시근로자")
    bad = T[i:].replace("9,386,032", "9,386,099", 1)   # (표3) 안 첫 자리 = 신생아 일반공급 맞벌이 150% 2인 금액을 67원 틀리게
    sp, unread = notice_pdf._pub_table_sp(bad)
    assert "newborn" not in sp and "newborn" in unread
    sp2, _ = notice_pdf._pub_table_sp(T[i:].replace("추첨공급(10%)", "추첨공급(15%)", 1))   # 다자녀 비율 합 105
    assert "multichild" not in sp2


def test_other_notices_have_no_pub_table_sp():
    for g in sorted((ROOT / "evidence/notices").glob("*.txt")):
        if g.stem == "2026000402":
            continue
        pl = notice_pdf.parse_pub_limits(g.read_text(encoding="utf-8")) or {}
        assert "sp_unread" not in pl and (pl.get("kind") != "pub_table"), g.stem
