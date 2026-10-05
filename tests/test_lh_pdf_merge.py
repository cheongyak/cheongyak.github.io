"""LH 공고문 여러 도구 읽기 합치기 (기능 lh_pdf_multi, app/lh_pdf_merge.py) — 규칙 단위 시험과 정답 데이터 대조."""
import json
from pathlib import Path

from app.lh_pdf_merge import merge_rents, merge_terms
from app.lh_terms import MEDIAN_2026

ROOT = Path(__file__).resolve().parents[1]


def T(**kw):
    base = {"relaxed": False, "homeless_relaxed": False, "homeless_max1": False, "income_basis": "도시근로자 월평균소득", "groups": [], "quotes": {},
            "income_table_100": None, "local": None}
    base.update(kw)
    return base


G = lambda key, **kw: {"key": key, "name": key, "homeless": "household", "income_pct": None, "asset_manwon": None, "car_manwon": None, **kw}


def test_fill_from_other_tool_when_first_missed():
    out, notes, conf = merge_terms({"pypdf": T(groups=[G("일반", car_manwon=None)]), "pdfium": T(groups=[G("일반", car_manwon=4542)]),
                                    "plumber": T(groups=[G("일반", car_manwon=4542)])})
    assert out["groups"][0]["car_manwon"] == 4542 and not conf and notes


def test_majority_wins_and_no_majority_is_unknown():
    out, _, conf = merge_terms({"pypdf": T(groups=[G("일반", asset_manwon=24500)]), "pdfium": T(groups=[G("일반", asset_manwon=24500)]),
                                "plumber": T(groups=[G("일반", asset_manwon=2450)])})
    assert out["groups"][0]["asset_manwon"] == 24500 and not conf
    out, _, conf = merge_terms({"pypdf": T(groups=[G("일반", asset_manwon=24500)]), "pdfium": T(groups=[G("일반", asset_manwon=2450)])})
    assert out["groups"][0]["asset_manwon"] is None and conf   # 둘이 다르면 모름 → 화면 '공고문 확인'


def test_phrase_found_by_any_tool():
    out, notes, _ = merge_terms({"pypdf": T(homeless_relaxed=False), "pdfium": T(homeless_relaxed=True)})
    assert out["homeless_relaxed"] is True and notes


def test_income_table_uses_tool_matching_constant():
    good = {str(k): v for k, v in MEDIAN_2026.items()}
    bad = dict(good, **{"2": 4619221})
    out, notes, _ = merge_terms({"pypdf": T(income_basis="기준 중위소득", income_table_100=bad), "plumber": T(income_basis="기준 중위소득", income_table_100=good)})
    assert out["income_table_100"] == good and notes


def test_groups_found_by_majority():
    out, _, _ = merge_terms({"pypdf": T(groups=[G("일반")]), "pdfium": T(groups=[G("일반"), G("청년")]), "plumber": T(groups=[G("일반"), G("청년")])})
    assert [g["key"] for g in out["groups"]] == ["일반", "청년"]
    out, _, _ = merge_terms({"pypdf": T(groups=[G("일반")]), "pdfium": T(groups=[G("일반"), G("고령자")]), "plumber": T(groups=[G("일반")])})
    assert [g["key"] for g in out["groups"]] == ["일반"]   # 한 도구만 찾은 계층은 넣지 않음


def test_rents_union_and_conflict():
    r = lambda t, g, d, m: {"complex": None, "type": t, "group": g, "deposit": d, "rent": m}
    out, _, conf = merge_rents({"pypdf": [r("26A", "가군", 100, 10)], "pdfium": [r("26A", "가군", 100, 10), r("36A", "가군", 200, 20)]})
    assert [(x["type"], x["deposit"]) for x in out] == [("26A", 100), ("36A", 200)] and not conf
    out, notes, conf = merge_rents({"pypdf": [r("26A", "가군", 100, 10)], "pdfium": [r("26A", "가군", 101, 10)]})
    assert out == [r("26A", "가군", 100, 10)] and notes and not conf   # 서로 다르면 기준 도구 표 (기록만)
    out, notes, _ = merge_rents({"pypdf": [], "pdfium": [], "plumber": [r("26A", "가군", 100, 10)]})
    assert out == [r("26A", "가군", 100, 10)] and notes   # 기준 도구가 못 읽으면 다른 도구


def test_rents_repeated_rows_kept_when_tools_agree():
    r = lambda t, g, d, m: {"complex": None, "type": t, "group": g, "deposit": d, "rent": m}
    rows = [r("39.75", "가군", 2747000, 54660), r("39.75", "가군", 2800000, 55000)]   # 단지가 다른 같은 주택형·구분 (부산 영구임대 818)
    out, notes, conf = merge_rents({"pypdf": rows, "pdfium": list(rows), "plumber": list(rows)})
    assert out == rows and not notes and not conf


def test_single_tool_is_unchanged():
    t = T(groups=[G("일반", car_manwon=4542)])
    out, notes, conf = merge_terms({"pypdf": t})
    assert out is t and not notes and not conf


def test_old_income_table_bug_is_corrected_by_other_tools(monkeypatch):
    """2026-10-05 에 고친 오류(pypdf 글에서 붙은 숫자 때문에 기준 중위소득 표를 110% 열로 읽음)를 일부러 되살려도,
    여러 도구로 읽으면 앱 고정값과 맞는 도구(pypdfium2·pdfplumber 칸 단위 표) 값을 고른다."""
    import re
    import app.lh_terms as LT
    from app.lh_pdf_merge import read_all
    from tools.qa.lh_pdf_tools import texts_of

    def old_income_table(t):
        m = re.search(r"소득구간\s?~30%\s?~50%\s?~70%\s?~100%", t)
        if not m:
            return None
        seg, out = t[m.end(): m.end() + 1500], {}
        for n in range(1, 9):
            r = re.search(rf"{n}인\s?([\d,]+)\s([\d,]+)\s([\d,]+)\s([\d,]+)\s", seg)
            if r:
                out[str(n)] = int(r.group(4).replace(",", ""))
        return out or None
    monkeypatch.setattr(LT, "income_table", old_income_table)
    want = {str(k): v for k, v in MEDIAN_2026.items()}
    for nid in ("2015122300020855", "2015122300020742"):
        tx = texts_of(nid)
        assert LT.parse_lh_terms(tx["pypdf"], "통합공공임대")["income_table_100"] != want   # 첫 도구만이면 틀림 (되살린 오류)
        tables = json.loads((ROOT / "evidence/lh/plumber" / f"{nid}.tables.json").read_text(encoding="utf-8"))
        assert read_all(tx, "통합공공임대", "", None, [], True, tables)["terms"]["income_table_100"] == want, nid
        assert read_all({"pypdf": tx["pypdf"]}, "통합공공임대", "", None, [], True, tables)["terms"]["income_table_100"] == want   # 칸 단위 표만으로도


def test_merged_never_wrong_against_golden():
    """정답 데이터가 있는 공고: 세 도구를 합친 값은 정답과 달라서는 안 되고, 첫 도구보다 맞은 칸이 적으면 안 된다 (tools/qa/lh_pdf_tools)."""
    import tools.qa.lh_pdf_tools as Q
    assert Q.main() == 0
    rep = json.loads((ROOT / "evidence/qa/lh-pdf-tools.json").read_text(encoding="utf-8"))
    s = rep["stat"]
    assert s["merged"]["ok"] >= s["pypdf"]["ok"] and s["merged"]["rent_ok"] >= s["pypdf"]["rent_ok"]
