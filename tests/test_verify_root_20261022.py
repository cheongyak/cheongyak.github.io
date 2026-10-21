"""2026-10-22 '베타 참고용' 반복 원인 정리 — 경고 이력(evidence/qa/warn-history.json, tools/qa/warn_history.py)에서 확인한 구조적 원인별 회귀 시험."""
import json
import pathlib

from tools.qa import invariants

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _row(**k):
    base = {"id": "2026000001-084.0000A", "category": "general", "supply_type": "APT", "kind": "APT", "price": 5.0, "area": 84.0,
            "households": 10, "notice": "2026-09-01", "apply": "2026-09-10", "apply_end": "2026-09-12", "winner": "2026-09-20", "sido": "서울"}
    base.update(k)
    return base


def test_zero_fetch_keeps_only_rows_within_retention():
    """원인 (10-06 00:03·10-08 00:27 실제): 자정 수집이 청약홈에서 0건을 받아 지난 결과를 통째로 다시 씀 → 발표 후 14일 지난 공고가 화면에 남음
    → 불변식 위반 1·13건 → 전체 '베타 참고용'. 일부 유형만 0건일 때(restore_missing_category)는 이미 보관 기간을 걸렀는데 전부 0건일 때만 빠져 있었다."""
    from datetime import date
    from app.pipeline import keep_previous
    rows = [_row(id="a", winner="2026-09-20"), _row(id="b", winner="2026-09-25"), _row(id="c", winner=None, apply_end="2026-10-07")]
    assert [x["id"] for x in keep_previous(rows, date(2026, 10, 4))] == ["a", "b", "c"]    # 09-20+14 = 10-04 까지 보관
    assert [x["id"] for x in keep_previous(rows, date(2026, 10, 5))] == ["b", "c"]
    assert [x["id"] for x in keep_previous(rows, date(2026, 10, 8))] == ["b"]


def test_zero_fetch_replay_20261008():
    """그날 실제 데이터(커밋 489dac05 docs/listings.json)로: 그대로 두면 위반 13, 보관 기간을 거르면 0"""
    import subprocess
    from datetime import date
    from app.pipeline import keep_previous
    r = subprocess.run(["git", "show", "489dac05:docs/listings.json"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        import pytest
        pytest.skip("얕은 clone 이라 그날 커밋이 없음")
    rows = json.loads(r.stdout)
    rows = rows["listings"] if isinstance(rows, dict) else rows
    name = "보관 기간 지난 공고가 목록에 남음"
    assert invariants.check(rows, "2026-10-08", True)["violations"][name]["count"] == 13
    assert name not in invariants.check(keep_previous(rows, date(2026, 10, 8)), "2026-10-08", True)["violations"]


def test_violations_keep_every_id():
    """화면이 위반 공고 하나하나에 '데이터 확인 필요'를 붙이려면 예시 5개가 아니라 전부 필요 (verify_scope)"""
    rows = [_row(id=f"2026000{n:03d}-084.0000A", price=None) for n in range(8)]
    v = invariants.check(rows, "2026-09-01", True)["violations"]["금액 범위 (억)"]
    assert v["count"] == 8 and len(v["examples"]) == 5 and len(v["ids"]) == 8
