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
