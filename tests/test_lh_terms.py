"""LH 임대 공고문 자격 조건 읽기(app/lh_terms.py) ↔ 정답 데이터(tests/golden/lh_rental.json, 공고문 원문을 읽어 확인).
규칙: 읽은 값은 정답과 같아야 한다. 못 읽은 값(None)은 화면이 '공고문 확인'으로 보여주므로 허용하되, 읽은 비율이 기준 아래로 떨어지면 실패.
evidence/lh/<공고ID>.txt 는 수집(app/lh_rental.py)이 한 번 저장하면 다시 쓰지 않는다."""
import json
import re
from pathlib import Path

from app.lh_terms import parse_lh_terms

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/lh_rental.json").read_text(encoding="utf-8"))["notices"]
KEYS = [("대학생", "대학생"), ("신혼부부·한부모", "신혼|한부모"), ("청년", "청년"), ("고령자", "고령자"), ("주거급여수급자", "주거급여"), ("일반", "일반")]


def _key(name):
    return next((k for k, p in KEYS if re.search(p, name)), name)


def _parsed(g):
    text = (ROOT / "evidence/lh" / f"{g['id']}.txt").read_text(encoding="utf-8", errors="replace")
    return parse_lh_terms(text, g["type"], g.get("verified_from", ""))


def test_golden_count():
    assert len(GOLD) >= 27


def test_golden_lh_terms_never_wrong():
    wrong, known, total = [], 0, 0
    for g in GOLD:
        r = _parsed(g)
        assert r["relaxed"] == g["relaxed"], (g["id"], "relaxed")
        assert r["homeless_relaxed"] == g["homeless_relaxed"], (g["id"], "homeless_relaxed")
        P = {x["key"]: x for x in r["groups"]}
        for gg in g["groups"]:
            p = P.get(_key(gg["name"]))
            for f in ("homeless", "income_pct", "asset_manwon", "car_manwon"):
                if gg[f] is None:
                    continue
                total += 1
                v = p and p.get(f)
                if v is None:
                    continue
                known += 1
                if v != gg[f]:
                    wrong.append((g["id"], gg["name"], f, v, gg[f]))
    assert not wrong, wrong
    assert known / total >= 0.85, (known, total)


def test_parsed_groups_exist_in_golden():
    """정답에 없는 계층을 만들어 내지 않는다"""
    for g in GOLD:
        names = {_key(x["name"]) for x in g["groups"]}
        for x in _parsed(g)["groups"]:
            assert x["key"] in names, (g["id"], x["key"])


def test_urban_income_constant_matches_notices():
    """판정에 쓰는 도시근로자 소득 100% 금액(화면 RENT_URBAN_2025, 수집 URBAN_2025) ↔ 공고문 표 (CLAUDE.md 4-6)"""
    from app.lh_terms import URBAN_2025
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    m = re.search(r"const RENT_URBAN_2025 = \[([\d, ]+)\]", html)
    assert m and [int(x) for x in m.group(1).split(",")] == [URBAN_2025[n] for n in range(1, 9)]
    # 행복주택 공고문 100% 열 (3~6인)
    for g in GOLD:
        if g["type"] == "행복주택" and g.get("income_table_100"):
            for k, v in g["income_table_100"].items():
                assert URBAN_2025[int(k)] == v, (g["id"], k)
    # 국민임대 원주태장4(740) 70%·80%·90% 표: 1인 90%, 2인 80%, 3~8인 70% 금액 = 100% × 비율 (원 단위 반올림 차이 1원 이내)
    t = re.sub(r"\s+", " ", (ROOT / "evidence/lh/2015122300020740.txt").read_text(encoding="utf-8"))
    for n in range(1, 9):
        row = re.search(rf"{n}인 ([\d,]+) ([\d,]+) ([\d,]+)", t)
        v70, v80, v90 = (int(x.replace(",", "")) for x in row.groups())
        assert abs(URBAN_2025[n] * 0.7 - v70) < 1 and abs(URBAN_2025[n] * 0.8 - v80) < 1 and abs(URBAN_2025[n] * 0.9 - v90) < 1, n


def _num_type(s):
    m = re.match(r"\d+(?:\.\d+)?", re.sub(r"\s", "", s or ""))
    return float(m.group(0)) if m else None


def test_golden_lh_rents():
    """보증금·월세(공고문 임대조건 표) ↔ 정답. 정답의 모든 줄을 같은 주택형(면적 숫자)으로 읽어야 하고, 정답에 없는 줄을 만들지 않는다.
    읽기 규칙: 임대보증금 계 = 계약금 + 잔금 인 네 숫자만 받는다(app/lh_terms.parse_lh_rents)."""
    from app.lh_terms import parse_lh_rents
    lst = {n["id"]: n["types"] for n in json.loads((ROOT / "tests/qa/lh/rental_units.json").read_text(encoding="utf-8"))}   # 공급 API 주택형 (2026-10-05 수집 고정본)
    total = 0
    for g in GOLD:
        text = (ROOT / "evidence/lh" / f"{g['id']}.txt").read_text(encoding="utf-8", errors="replace")
        rows = parse_lh_rents(text, lst[g["id"]])
        for gr in g["rents"]:
            total += 1
            assert any((r["deposit"], r["rent"]) == (gr["deposit"], gr["rent"]) and _num_type(r["type"]) == _num_type(gr["type"]) for r in rows), (g["id"], gr)
        gold_pairs = {(x["deposit"], x["rent"]) for x in g["rents"]}
        extra = [r for r in rows if (r["deposit"], r["rent"]) not in gold_pairs]
        assert not extra, (g["id"], extra)
    assert total >= 140
