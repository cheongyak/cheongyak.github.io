"""한 단지가 비교 거래를 독차지하지 않게 (기능 market_complex_balance, 2026-10-31 운영자 '한 단지가 거래 독차지 못하게').
단지마다 거래가 5건보다 많으면 그 단지 거래 무게를 5/건수로 줄여 중앙값·하위 25% 를 매긴다. 수집(app/market.mid_low)과 원자료 대조(tools/qa/market_check.stats)는 따로 쓴 계산."""
import json
import random
import statistics
from pathlib import Path

import pytest

from app import market as M
from tools.qa import market_check as MC

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bal():
    M.BALANCE = True; MC.BAL["on"] = True
    yield
    M.BALANCE = False; MC.BAL["on"] = False


def test_equal_weights_match_current_quantiles():
    """무게가 모두 같으면 지금 계산(_p25·statistics.median)과 같다 — 모든 단지가 5건 이하인 공고는 시세가 그대로"""
    rnd = random.Random(7)
    for n in range(1, 40):
        xs = [rnd.uniform(1, 30) for _ in range(n)]
        assert M._wq(xs, [1.0] * n, 0.5) == pytest.approx(statistics.median(xs), abs=1e-9)
        assert M._wq(xs, [1.0] * n, 0.25) == pytest.approx(M._p25(xs), abs=1e-9)


def test_off_and_small_complexes_unchanged(bal):
    rows = [{"apt": f"단지{i % 6}", "umd": "원천동", "amount": 90000 + i * 1000} for i in range(30)]   # 6개 단지 × 5건
    a = [r["amount"] for r in rows]
    assert M._summary(a, rows) == (round(M._p25(a) / 10000, 2), round(statistics.median(a) / 10000, 2)) and M.cap_note(rows) == ""
    one = [{"apt": "한단지", "umd": "원천동", "amount": 80000 + i * 500} for i in range(20)]   # 한 단지뿐이면 무게가 같아 그대로
    b = [r["amount"] for r in one]
    assert M._summary(b, one) == (round(M._p25(b) / 10000, 2), round(statistics.median(b) / 10000, 2))


def test_gwanggyo_real_case(bal):
    """광교 자연앤 센트레빌 84A (2026000528): 57건 중 22건이 영흥숲 푸르지오 파크비엔(9억 안팎) → 하위 25% 9.5억(비추천).
    단지 몫 5건 상한이면 하위 25% 12.11억, 중앙값 14.8억 그대로"""
    fx = json.loads((ROOT / "tests/qa/market_balance_case.json").read_text(encoding="utf-8"))
    rows = fx["trades"]
    a = [r["amount"] for r in rows]
    M.BALANCE = False
    assert M._summary(a, rows) == (fx["old"]["low"], fx["old"]["base"])
    M.BALANCE = True
    assert M._summary(a, rows) == (12.11, 14.8)
    assert "영흥숲푸르지오파크비엔 22건" in M.cap_note(rows)


def test_app_matches_independent_check(bal):
    rnd = random.Random(11)
    for _ in range(300):
        rows = [{"apt": f"단지{rnd.randint(0, 4)}", "umd": rnd.choice(["원천동", "이의동 1"]), "amount": rnd.randint(50000, 200000), "area": 84.9}
                for _ in range(rnd.randint(1, 60))]
        a = [r["amount"] for r in rows]
        m, q = MC.stats(a, rows)
        am, aq = M.mid_low(a, rows)
        assert am == pytest.approx(m) and (aq is None) == (q is None) and (aq is None or aq == pytest.approx(q))


def test_nearby_result_uses_cap(bal):
    from app.market_nearby import _result
    fx = json.loads((ROOT / "tests/qa/market_balance_case.json").read_text(encoding="utf-8"))
    rows = [dict(r, build_year=2023) for r in fx["trades"]]
    out = _result(rows, 0, 84.76, "newbuild", "dong", "같은 동(원천동) 2km 안")
    assert (out["mkt_low"], out["mkt_base"]) == (12.11, 14.8) and "5건 몫으로 줄여 계산" in out["mkt_note"]
