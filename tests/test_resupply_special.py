"""재공급 주택형별 특별공급 세대수 (기능: resupply_special, 2026-10-02 블라인드 감사에서 재공급 0세대 주택형이 모두 '확인 필요'로만 나오던 문제)."""
import json
import pathlib

from app import notice_pdf

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLD = json.loads((ROOT / "tests" / "golden" / "notices.json").read_text(encoding="utf-8"))


def test_golden_resupply_sp_table():
    for no in ("2026930036", "2026930035", "2026930031", "2026930038"):   # 2026930038: 특공 '계' 칸이 없는 표 (W41 블라인드 표본)
        t = (ROOT / "evidence" / "notices" / f"{no}.txt").read_text(encoding="utf-8")
        assert notice_pdf.parse_sp_table(t) == GOLD[no]["parse"]["sp_table"], no


def test_sp_table_no_sum_rejects_rows_that_do_not_add_up():
    t = "총공급 세대수 노부모 부양 특별공급 일반공급주거 전용면적 주거 공용면적 소계 2026930099 01 084.0000A 84A 84.0 25.0 109.0 50.0 159.0 50.0 4 3 2 합 계"
    assert notice_pdf.parse_sp_table(t) is None          # 3+2 ≠ 4 → 읽지 않음
    ok = t.replace("4 3 2", "4 3 1")
    assert notice_pdf.parse_sp_table(ok) == {"084.0000A": {"elder": 3, "total": 3}}


def test_sp_table_rejects_rows_that_do_not_add_up():
    t = "총공급 세대수 특별공급 세대수 주거 전용면적 소계 신혼부부 노부모부양 계 2026930099 01 084.0000A 84A 84.0 25.0 109.0 50.0 159.0 50.0 2 1 1 3 합 계"
    assert notice_pdf.parse_sp_table(t) is None          # 1+1 ≠ 3 → 읽지 않음
