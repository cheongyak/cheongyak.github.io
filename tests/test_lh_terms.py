"""LH 임대 공고문 자격 조건 읽기(app/lh_terms.py) ↔ 정답 데이터(tests/golden/lh_rental.json, 공고문 원문을 읽어 확인).
규칙: 읽은 값은 정답과 같아야 한다. 못 읽은 값(None)은 화면이 '공고문 확인'으로 보여주므로 허용하되, 읽은 비율이 기준 아래로 떨어지면 실패.
evidence/lh/<공고ID>.txt 는 수집(app/lh_rental.py)이 한 번 저장하면 다시 쓰지 않는다."""
import json
import re
from pathlib import Path

from app.lh_terms import parse_lh_terms

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/lh_rental.json").read_text(encoding="utf-8"))["notices"]
KEYS = [("장기종사자", "장기종사자"), ("대학생", "대학생"), ("신혼부부·한부모", "신혼|한부모"), ("청년", "청년"), ("고령자", "고령자"), ("주거급여수급자", "주거급여"), ("일반", "일반")]


def _key(name):
    return next((k for k, p in KEYS if re.search(p, name)), name)


REGION = {n["id"]: n.get("region") for n in json.loads((ROOT / "tests/qa/lh/rental_units.json").read_text(encoding="utf-8"))}


def _parsed(g):
    text = (ROOT / "evidence/lh" / f"{g['id']}.txt").read_text(encoding="utf-8", errors="replace")
    return parse_lh_terms(text, g["type"], g.get("verified_from", ""), REGION.get(g["id"]))


def test_golden_count():
    assert len(GOLD) >= 27


def test_golden_lh_terms_never_wrong():
    wrong, known, total = [], 0, 0
    for g in GOLD:
        r = _parsed(g)
        assert r["relaxed"] == g["relaxed"], (g["id"], "relaxed")
        assert r["homeless_relaxed"] == g["homeless_relaxed"], (g["id"], "homeless_relaxed")
        if "homeless_max1" in g:
            assert r["homeless_max1"] == g["homeless_max1"], (g["id"], "homeless_max1")
        for k in ("regions", "account"):     # 공공임대: 거주지역·청약통장 순위
            if k in g:
                assert r.get(k) == g[k], (g["id"], k, r.get(k))
        if "local" in g:                      # 신청자격 거주 요건 (영구임대 '○○시에 거주하는 성년자인 무주택세대구성원')
            loc = r.get("local")
            assert (loc and {k: loc[k] for k in ("name", "sido", "sigun")}) == (g["local"] or None), (g["id"], "local", loc)
        if "account_by_movein_groups" in g:   # 행복주택 청년·신혼부부 '입주 전까지 주택청약종합저축 가입 증명'
            assert sorted(x["key"] for x in r["groups"] if x.get("account_by_movein")) == g["account_by_movein_groups"], (g["id"], "account_by_movein")
        P = {x["key"]: x for x in r["groups"]}
        for gg in g["groups"]:
            p = P.get(_key(gg["name"]))
            if gg.get("job_regions"):
                assert p and p.get("job_regions") == gg["job_regions"], (g["id"], gg["name"], "job_regions")
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


def test_golden_income_table_100():
    """소득 100% 금액표·8인 초과 1인당 금액 = 원문 (2026-10-05: 기준 중위소득 표에서 붙은 숫자 때문에 칸이 밀려 110%·120% 열을 읽던 오류)"""
    from app.lh_terms import MEDIAN_2026, MEDIAN_ADD_2026
    n = 0
    for g in GOLD:
        r = _parsed(g)
        if g.get("income_table_100") and (r.get("income_table_100") or g["type"] in ("통합공공임대", "행복주택")):   # 국민·영구임대는 표를 읽지 않음(고정값 URBAN_2025 로 판정)
            n += 1
            mine = {k: v for k, v in (r.get("income_table_100") or {}).items() if k in g["income_table_100"]}   # 행복주택 3~6인 표만 정답에 있음
            assert mine == g["income_table_100"], (g["id"], r.get("income_table_100"))
        if "income_add_per" in g:
            assert r.get("income_add_per") == g["income_add_per"], (g["id"], "income_add_per")
        if g["type"] == "통합공공임대" and g.get("income_table_100"):
            assert {int(k): v for k, v in g["income_table_100"].items()} == MEDIAN_2026, g["id"]
            assert g.get("income_add_per") == MEDIAN_ADD_2026, g["id"]
    assert n >= 4
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert "income_add_per" in html   # 화면이 9인 이상에 8인 초과 금액을 쓴다


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


def test_golden_dual_add():
    """맞벌이 가산(dual_add) = 정답 데이터 income_dual_pct − income_pct (원문 확인값). 여러 도구를 합친 값으로 본다 (742 는 pypdf 글에 문장이 빠짐).
    정답에 맞벌이 기준이 없는 계층은 가산을 지어내면 안 된다 (2026-10-05: 화면이 유형별 기본 가산을 쓰던 것을 없앰)."""
    from app.lh_pdf_merge import read_all
    from tools.qa.lh_pdf_tools import texts_of
    seen = 0
    for g in GOLD:
        m = read_all(texts_of(g["id"]), g["type"], g.get("verified_from", ""), REGION.get(g["id"]), [], True)
        P = {x["key"]: x for x in (m["terms"] or {}).get("groups", [])}
        for gg in g["groups"]:
            p = P.get(_key(gg["name"])) or {}
            dp, ip = gg.get("income_dual_pct"), gg.get("income_pct")
            if dp and isinstance(ip, dict) and ip.get("3+"):
                seen += 1
                assert p.get("dual_add") == dp["3+"] - ip["3+"], (g["id"], gg["name"], p.get("dual_add"))
            elif p.get("dual_add") is not None and not any(_key(o["name"]) == _key(gg["name"]) and o.get("income_dual_pct") for o in g["groups"]):
                # (742 는 신혼부부·한부모가족을 한 계층으로 읽는다. 한부모는 배우자가 없어 화면이 맞벌이를 적용하지 않는다)
                assert False, (g["id"], gg["name"], "정답에 없는 맞벌이 가산", p.get("dual_add"))
    assert seen >= 4


def test_prewed_and_unknown_groups():
    from app.lh_terms import unknown_happy_groups
    assert unknown_happy_groups("3-1. 대학생 계층 … 3-2. 청년 계층 … 3-6. 산업단지 근로자 계층 신청자격") == ["산업단지 근로자"]
    assert unknown_happy_groups("3-1. 대학생 계층 3-2. 청년 계층 3-3. 신혼부부ㆍ한부모가족 계층 3-4. 고령자 계층 3-5. 주거급여수급자 계층") == []
    for g in GOLD:
        if any("신혼" in x["name"] for x in g["groups"]):
            t = (ROOT / "evidence/lh" / f"{g['id']}.txt").read_text(encoding="utf-8", errors="replace")
            assert _parsed(g).get("prewed_ok") == bool(re.search(r"예비\s?신혼부부", t)), g["id"]


def test_public_excluded_needs_evidence():
    """공공임대 신청자격 절에 '소득' 글자가 없다는 이유로 소득·자산을 미적용으로 보는 것은, 그 절을 제대로 찾았다는 근거(무주택·거주지역·
    청약통장)가 함께 읽혔을 때만 (절을 잘못 잡으면 소득·자산을 보지 않고 '가능'이 될 수 있다)."""
    for g in GOLD:
        if g["type"] != "공공임대":
            continue
        r = _parsed(g)
        for x in r["groups"]:
            if x.get("income_pct") == "excluded":
                assert x.get("homeless") and r.get("regions") is not None and r.get("account"), g["id"]
    bare = "신청자격 입주자모집공고일 현재 무주택세대구성원 으로서 아래 요건을 갖춘 분 " * 20
    r = parse_lh_terms(bare, "공공임대")
    assert all(x.get("income_pct") != "excluded" for x in r["groups"]), r["groups"]


def test_local_unread_failsafe():
    """신청자격 거주 요건 문장('공고일 현재 ○○에 거주하는 성년자')이 보이는데 지역을 읽지 못하면 local_unread 로 남겨 화면이 '확인'으로 둔다.
    정답 공고에서는 생기면 안 된다(거주 요건을 읽었거나 요건이 없는 공고)."""
    for g in GOLD:
        assert not _parsed(g).get("local_unread"), g["id"]
    r = parse_lh_terms("3. 신청자격 모집공고일 현재 갈말읍에 거주하는 성년자인 무주택세대구성원으로서 " * 3, "영구임대", "", "강원특별자치도")
    assert r.get("local") is None and r.get("local_unread")
    r = parse_lh_terms("신청자격 공고일 현재 국내에 거주하는 성년자인 무주택세대구성원 " * 3, "영구임대", "", None)
    assert not r.get("local_unread")
