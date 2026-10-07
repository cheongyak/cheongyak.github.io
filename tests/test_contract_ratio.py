"""공고문 분양대금 비율·계약금 나눔 (기능 contract_from_notice, 2026-10-08 제보 '계약금이 모든 공고 10% 고정').
정답: tests/golden/notices.json fields.pay_ratio·contract_split (공고문 공급금액 표를 사람이 읽은 값)."""
import json
from pathlib import Path

from app.notice_pdf import parse_notice

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))


def _p(n):
    return parse_notice((ROOT / "evidence/notices" / f"{n}.txt").read_text(encoding="utf-8"))


def test_golden_pay_ratio():
    n = 0
    for nid, g in GOLD.items():
        f = g["fields"]
        if "pay_ratio" not in f:
            continue
        r = _p(nid)
        assert r.get("pay_ratio") == f["pay_ratio"], nid
        cs = r.get("contract_split")
        want = f.get("contract_split")
        assert (cs and {k: cs.get(k) for k in want}) == want if want else cs is None, (nid, cs)
        n += 1
    assert n >= 4


def test_option_tables_are_not_supply_price():
    """발코니 확장·추가선택품목 표의 '계약금(10%) 잔금(90%)'는 분양대금이 아니다 (2026000468)"""
    assert _p("2026000468")["pay_ratio"]["contract"] == 0.05


def test_split_needs_constant_first_amount():
    """1차 계약금이 줄마다 다르면(정액이 아님) 나뉜 것으로 적지 않는다"""
    t = (ROOT / "evidence/notices/2026910256.txt").read_text(encoding="utf-8").replace("10,000,000 66,350,000", "11,000,000 65,350,000", 1)
    assert parse_notice(t).get("contract_split") is None


def test_unreadable_header_leaves_default():
    t = (ROOT / "evidence/notices/2026000463.txt").read_text(encoding="utf-8").replace("계약금(5%)", "계약금")
    assert "pay_ratio" not in parse_notice(t)
