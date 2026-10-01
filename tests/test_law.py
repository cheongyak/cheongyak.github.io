"""법령 원문 ↔ 앱·검증 기준 대조 — 「주택공급에 관한 규칙」 별표 1(가점제 적용기준)·별표 2(민영주택 청약 예치기준금액).

원문은 법제처 OPEN API 로 매주 받아 evidence/law/rule.xml 에 남는다 (tools/law_probe.py, law-probe.yml).
법령이 바뀌어 앱 고정값(ACCOUNT_DEPOSIT)이나 판정 검증 기대값 계산(tools/make_judge_cases.score)과 달라지면 이 테스트가 실패하고,
매일 수집 실행이 실패해 이슈로 알린다. 판정 화면 함수 ↔ make_judge_cases 는 판정 검증 사례 144건이 따로 맞춰 본다.
"""
import json
import re
from datetime import date
from pathlib import Path

import pytest

from tools import build_static
from tools.make_judge_cases import score

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "evidence" / "law" / "rule.xml").exists(), reason="법령 원문 없음")


def _sub(ref: str, years: int = 0, months: int = 0) -> str:
    y, m, d = map(int, ref.split("-"))
    total = y * 12 + (m - 1) - years * 12 - months
    return date(total // 12, total % 12 + 1, min(d, 28)).isoformat()


def test_law_deposit_equals_app():
    lt = build_static.law_tables()
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    app = json.loads(re.sub(r"(\w+):", r'"\1":', re.search(r"const ACCOUNT_DEPOSIT = (\{[^;]+\});", html).group(1)))
    law = {k: [lt["deposit"][a][k] for a in ("85", "102", "135", "all")] for k in ("seoul_busan", "metro", "other")}
    assert law == app, f"법령 별표 2 {law} ≠ 앱 ACCOUNT_DEPOSIT {app}"


def test_law_score_table_equals_oracle():
    lt = build_static.law_tables()
    pairs = lt["score_pairs"]
    assert len(pairs) == 40, "별표 1 가점 산정기준 표 모양이 바뀌었음 — 원문을 다시 확인"
    nohome, dep, acct = pairs[:16], pairs[16:23], pairs[23:]
    ref = "2026-09-18"
    for label, pts in nohome:      # 무주택기간: 만 30세부터 y년
        y = 0 if label == "1년 미만" else int(re.match(r"(\d+)년", label).group(1))
        p = {"birth": _sub(ref, 30 + y, 1), "dependents": 0, "acctSince": _sub(ref, 1)}
        assert score(p, ref)[0] == int(pts), f"무주택기간 {label}: 법령 {pts}점 ≠ 계산 {score(p, ref)[0]}점"
    for label, pts in dep:         # 부양가족 수
        n = int(re.match(r"(\d+)", label).group(1))
        p = {"birth": "1980-01-01", "dependents": n, "acctSince": _sub(ref, 1)}
        assert score(p, ref)[1] == int(pts), f"부양가족 {label}: 법령 {pts}점"
    for label, pts in acct:        # 주택청약종합저축 가입기간
        m = 3 if label == "6개월 미만" else 8 if label.startswith("6개월 이상") else int(re.match(r"(\d+)년", label).group(1)) * 12 + 1
        p = {"birth": "1980-01-01", "dependents": 0, "acctSince": _sub(ref, 0, m)}
        assert score(p, ref)[2] == int(pts), f"통장 가입기간 {label}: 법령 {pts}점 ≠ 계산 {score(p, ref)[2]}점"
    t1 = lt["tables"]["1"]["body"]
    assert "50퍼센트" in t1 and "3점을 초과하는 경우에는 3점" in t1 and "17\n" not in t1[:0]   # 배우자 통장 50%·최대 3점 (비고 2)


def test_guides_cite_law_not_notices():
    sc, dp = build_static.guide_score(), build_static.guide_deposit()
    assert "[별표 1] 가점제 적용기준" in sc and "더샵 분당하이스트" not in sc and "모집공고문 가점표" not in sc
    assert "[별표 2] 민영주택 청약 예치기준금액" in dp and "광명 시티프라디움" not in dp
    assert "<td>1,500</td><td>1,000</td><td>500</td>" in dp and "<td>15년 이상</td><td>32</td>" in sc and "<td>15년 이상</td><td>17</td>" in sc
    assert "법령 시행 2026.6.15." in sc and "별표 개정 2024.12.18." in sc and "별표 개정 2023.5.10." in dp


def _article(no: str) -> str:
    import xml.etree.ElementTree as ET
    root = ET.parse(ROOT / "evidence" / "law" / "rule.xml").getroot()
    for j in root.iter("조문단위"):
        if (j.findtext("조문번호") or "").strip() == no and not (j.findtext("조문가지번호") or "").strip() and (j.findtext("조문여부") or "") == "조문":
            return " ".join(t.strip() for t in j.itertext() if t.strip())
    raise AssertionError(f"제{no}조를 찾지 못함")


def test_law_inelig_ban_equals_app():
    """부적격 방지 체크(inelig_check)가 보여주는 당첨 제한 기간 = 제58조제3항 원문."""
    t = _article("58")
    assert "1. 수도권: 1년" in t and "2. 수도권 외의 지역: 6개월(투기과열지구 및 청약과열지역은 1년으로 한다)" in t and "위축지역: 3개월" in t, "제58조③ 문구가 바뀜 — 원문 확인 후 앱 INELIG_BAN 과 함께 고칠 것"
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    app = re.search(r"const INELIG_BAN = (\{[^;]+\});", html).group(1)
    assert app == "{ capital:'1년', other:'6개월', hot:'1년', cool:'3개월' }"


def test_law_inelig_facts_present():
    """부적격 방지 체크 설명이 기대는 원문 문구가 그대로 있는지 (제4조⑦ 국외 거주, 제28조① 규제지역 1순위, 제53조 분양권·60세 직계존속, 제55조 특공 한 차례)."""
    assert "국외에 계속하여 90일을 초과하여 거주한 기간" in _article("4") and "연간 183일을 초과하는 기간" in _article("4")
    t28 = _article("28")
    assert "2) 세대주일 것" in t28 and "과거 5년 이내 다른 주택의 당첨자가 된 자의 세대에 속한 자가 아닐 것" in t28
    t53 = _article("53")
    assert "분양권등을 갖고 있거나" in t53 and "60세 이상의 직계존속(배우자의 직계존속을 포함한다)" in t53 and "제46조" in t53
    assert "한 차례에 한정하여" in _article("55")
