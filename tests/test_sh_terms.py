"""SH 공고문 신청자격 읽기 (app/sh_terms.py, 기능 sh_judge) — 정답 데이터(tests/golden/sh_rental.json terms)와 대조."""
import json
from pathlib import Path

from app.sh_terms import parse_sh_terms, parse_newlywed, parse_youth

ROOT = Path(__file__).resolve().parents[1]
GOLD = json.loads((ROOT / "tests/golden/sh_rental.json").read_text(encoding="utf-8"))["notices"]


def _text(seq):
    return (ROOT / "evidence/sh" / f"{seq}.txt").read_bytes().decode("utf-8", "replace")


def _strip(t):
    """비교에서 뺄 칸: 공고문 인용·이름·읽기 문제 목록"""
    t = {k: v for k, v in t.items() if k not in ("quote", "issues")}
    t["groups"] = [{k: v for k, v in g.items() if k != "name"} for g in t["groups"]]
    return t


def test_golden_sh_terms():
    n = 0
    for g in GOLD:
        if "terms" not in g:
            continue
        got = parse_sh_terms(_text(g["seq"]), g["type"])
        assert got is not None, g["seq"]
        if g["type"] != "사회주택":   # 사회주택은 일부 기준을 일부러 비운 공고가 있어(읽기 문제 목록 있음) 값만 비교
            assert got["issues"] == [], (g["seq"], got["issues"])
        assert _strip(got) == _strip(g["terms"]), g["seq"]
        n += 1
    assert n >= 5


def test_unsupported_kinds_have_no_terms():
    for g in GOLD:
        if g["type"] not in ("신혼·신생아 매입임대", "청년 매입임대", "장기전세", "사회주택"):
            assert parse_sh_terms(_text(g["seq"]), g["type"]) is None, g["seq"]


def test_income_table_mismatch_blanks_income():
    """공고문 소득표 금액이 앱의 도시근로자 2025 × 퍼센트와 다르면 소득 기준을 비운다(→ 화면 '공고문 확인')"""
    t = _text("310650").replace("4,693,016", "4,793,016")
    r = parse_newlywed(t)
    assert r["issues"] and all(g["income_pct"] is None for g in r["groups"] if g["key"] != "지원대상한부모")
    t = _text("310950").replace("4,576,036", "4,576,999")
    assert parse_youth(t)["groups"][0]["income_pct"] is None


def test_exempt_needs_sentence():
    """'지원대상 한부모가족 … 소득·자산검증 불필요' 문장이 없으면 면제로 보지 않는다"""
    t = _text("310650").replace("자산검증 불필요", "자산검증 필요")
    g = [x for x in parse_newlywed(t)["groups"] if x["key"] == "지원대상한부모"][0]
    assert g["exempt"] is False and g["income_pct"] == {"2": 80, "3+": 70}


def test_youth_without_single_sentence_flags_issue():
    t = _text("310950").replace("혼인 중이 아닐 것", "").replace("미혼의 청년", "청년")
    r = parse_youth(t)
    assert "미혼 요건 문장 못 찾음" in r["issues"]


def test_jeonse_schedule_golden():
    """장기전세 순위별 접수일 (기능 sh_jeonse) — 정답 tests/golden/sh_rental.json ranks"""
    from app.sh_terms import jeonse_schedule
    n = 0
    for g in GOLD:
        if "ranks" in g:
            assert jeonse_schedule(_text(g["seq"]), g["posted"]) == g["ranks"], g["seq"]
            n += 1
    assert n >= 1


def test_jeonse_income_table_mismatch_blanks_income():
    """장기전세 소득표 금액이 도시근로자 2025 × % 와 다르면 소득 기준을 비운다(→ 화면 '공고문 확인')"""
    from app.sh_terms import parse_jeonse
    t = _text("309467").replace("8,576,850원", "8,676,850원")
    r = parse_jeonse(t)
    assert r["issues"] and all(g["income_pct"] is None for g in r["groups"])
    t = _text("309467").replace("상기의 출생자녀에 따른 가산과 중복적용되지 않음", "")
    assert all(g["income_pct"] is None for g in parse_jeonse(t)["groups"])   # 맞벌이·출산 가산 중복 여부를 모르면 소득 판정 안 함


def test_mirinae_not_read_as_jeonse():
    """미리내집(장기전세Ⅱ)은 신혼·출산 가구 대상이라 기준이 달라 읽지 않는다"""
    from app.sh_terms import parse_jeonse
    assert parse_jeonse("미리내집(장기전세주택Ⅱ) 입주자 모집 " + _text("309467")) is None


def test_social_unread_notices_stay_unsupported():
    """사회주택 중 형식이 섞이거나 기준이 둘인 공고는 읽지 않는다(→ 화면 '판정 미지원') — 정답 데이터 social_unread"""
    from app.sh_terms import parse_social
    d = json.loads((ROOT / "tests/golden/sh_rental.json").read_text(encoding="utf-8"))
    for seq in d["social_unread"]:
        assert parse_social(_text(seq)) is None, seq


def test_social_wrong_income_table_blanks_income():
    """사회주택 소득표가 도시근로자 2025 × % 와 다르면(지난해 표·다른 비율) 소득을 비운다 — 310037 표를 1천원 바꾸면 비움"""
    from app.sh_terms import parse_social
    r = parse_social(_text("310037").replace("7,039천원", "7,139천원"))
    assert all(g["income_pct"] is None for g in r["groups"])
    r = parse_social(_text("310037").replace("세대 구성원 전원의 세전소득", "본인의 세전소득"))
    assert all(g["income_pct"] is None for g in r["groups"])
