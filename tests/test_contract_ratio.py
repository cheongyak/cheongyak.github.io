"""공고문 분양대금 비율·계약금 나눔 (기능 contract_from_notice, 2026-10-08 제보 '계약금이 모든 공고 10% 고정').
정답: tests/golden/notices.json fields.pay_ratio·contract_split (공고문 공급금액 표를 사람이 읽은 값)."""
import json
from pathlib import Path

from app.notice_pdf import parse_notice

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))


def _p(n):
    from tools.qa.pay_audit import originals
    return parse_notice(originals()[n].read_text(encoding="utf-8"))


def test_golden_pay_ratio():
    n = 0
    for nid, g in GOLD.items():
        f = g["fields"]
        if "pay_ratio" not in f:
            continue
        r = _p(nid)
        assert r.get("pay_ratio") == f["pay_ratio"], (nid, r.get("pay_ratio"))
        cs = r.get("contract_split")
        want = f.get("contract_split")
        assert (cs and {k: cs.get(k) for k in want}) == want if want else cs is None, (nid, cs)
        n += 1
    assert n >= 17


def test_option_tables_are_not_supply_price():
    """발코니 확장·추가선택품목 표의 '계약금(10%) 잔금(90%)'는 분양대금이 아니다 (2026000468)"""
    assert _p("2026000468")["pay_ratio"]["contract"] == 0.05


def test_split_needs_constant_first_amount():
    """1차 계약금이 줄마다 다르면(정액이 아님) 나뉜 것으로 적지 않는다"""
    t = (ROOT / "evidence/notices/2026910256.txt").read_text(encoding="utf-8").replace("10,000,000 66,350,000", "11,000,000 65,350,000", 1)   # 한 줄만 1차 금액을 바꿈
    assert parse_notice(t).get("contract_split") is None


def test_unreadable_header_leaves_default():
    t = (ROOT / "evidence/notices/2026000463.txt").read_text(encoding="utf-8").replace("계약금(5%)", "계약금")
    assert "pay_ratio" not in parse_notice(t)


def test_audit_finds_no_mismatch():
    """독립 점검(tools/qa/pay_audit.py): 읽은 계약금 % 를 공고문 금액 줄이 뒷받침해야 한다 — 머리 글자만 보고 읽는 실수 재발 방지"""
    from tools.qa import pay_audit as PA
    from app.notice_pdf import parse_notice as pn
    bad = []
    for n, f in PA.originals().items():
        t = f.read_text(encoding="utf-8", errors="replace")
        pr = pn(t).get("pay_ratio")
        if pr and PA.row_rates(t).get(round(pr["contract"] * 100), 0) == 0:
            bad.append(n)
    assert not bad, bad


def test_header_alone_is_not_enough():
    """표 머리만 있고 금액 줄이 그 비율과 맞지 않으면 읽지 않는다 (2026000437 발코니 확장 표 '계약금(10%) 중도금(10%) 잔금(80%)' 같은 경우)"""
    t = "■ 공급금액 및 납부일정 (단위:원) 공급금액 계약금(10%) 중도금(10%) 잔금(80%) 84A 6,953,000 695,300 695,300 5,562,400"
    assert "pay_ratio" not in parse_notice(t)
    t2 = "■ 공급금액 및 납부일정 (단위:원) 공급금액 계약금(10%) 중도금(60%) 잔금(30%) 84A 520,000,000 52,000,000 52,000,000 52,000,000"
    assert parse_notice(t2)["pay_ratio"] == {"contract": 0.1, "mid": 0.6, "balance": 0.3}


def test_thousand_unit_fallback_needs_main_table():
    """단위 표시가 멀리 있는 천원 표(2026820009)는 '주택가격' 열 바로 뒤 머리이고 3줄 이상 맞을 때만 천원으로 읽는다 — 원 단위 옵션 표를 천 배로 읽지 않게"""
    rows = " ".join(f"{t:,} {t // 10:,} {t // 10 * 2:,} {t - t // 10 * 3:,}" for t in (384460, 358160, 381030))
    t = "분양가격 및 납부조건 주택형 타입 층별 주택가격 계약금10% 중도금20% 잔금 " + rows
    assert parse_notice(t)["pay_ratio"] == {"contract": 0.1, "mid": 0.2, "balance": 0.7}
    t2 = "■ 발코니확장 공급금액 품목 계약금10% 중도금20% 잔금 " + rows   # 같은 금액이라도 본 표 열 이름이 없으면 천원으로 보지 않음
    assert "pay_ratio" not in parse_notice(t2)
    t3 = "분양가격 주택형 주택가격 계약금10% 중도금20% 잔금 384,460 38,446 76,892 268,122"   # 1줄만 맞으면 안 읽음
    assert "pay_ratio" not in parse_notice(t3)
