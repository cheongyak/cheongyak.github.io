"""LH 임대 불변식 검사(tools/qa/lh_invariants.py)가 일부러 망가뜨린 데이터를 잡는지."""
import copy
import json
from pathlib import Path

from tools.qa.lh_invariants import check

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/lh_rental.json").read_text(encoding="utf-8"))["notices"]


def _base():
    return {"notices": [{"id": "X1", "type": "국민임대", "judge_type": True, "name": "시험",
                         "schedule": [{"complex": "A", "apply_start": "2026-10-01", "apply_end": "2026-10-03", "docs_target": "2026-10-20", "winner": "2026-12-01"}],
                         "rents": [{"type": "39", "group": None, "deposit": 10_000_000, "rent": 100_000}],
                         "terms": {"income_basis": "도시근로자 월평균소득", "income_table_100": {"3": 8168429},
                                   "groups": [{"key": "일반", "homeless": "household", "income_pct": {"1": 90, "2": 80, "3+": 70}, "asset_manwon": 34500, "car_manwon": 4542}]}}]}


def test_clean_passes():
    assert check(_base(), GOLD) == {}


def test_catches_broken_values():
    d = copy.deepcopy(_base()); N = d["notices"][0]
    N["schedule"][0]["apply_end"] = "2026-09-01"
    N["rents"][0]["deposit"] = 50_000
    N["terms"]["groups"][0]["income_pct"] = {"1": 70, "2": 80, "3+": 90}
    N["terms"]["groups"][0]["asset_manwon"] = 345_000
    N["terms"]["income_table_100"] = {"3": 8000000}
    v = check(d, GOLD)
    assert {"schedule_order", "rent_deposit_range", "income_pct_order", "asset_range", "urban_table"} <= set(v)


def test_catches_golden_mismatch():
    g = next(x for x in GOLD if x["id"] == "2015122300020740")
    d = {"notices": [{"id": g["id"], "type": "국민임대", "judge_type": True, "name": "", "schedule": [], "rents": [],
                      "terms": {"groups": [{"key": "일반", "homeless": "household", "income_pct": {"1": 90, "2": 80, "3+": 70}, "asset_manwon": 24500, "car_manwon": 4542}]}}]}
    assert "golden" in check(d, GOLD)


def test_unread_terms():
    d = copy.deepcopy(_base()); d["notices"][0]["terms"] = None
    assert "terms_unread" in check(d, GOLD)
