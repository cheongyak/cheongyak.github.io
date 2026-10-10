"""공공분양식 공공임대 특별공급 소득표 (기능 rental_pub_table_sp, 2026-10-10 사용자 'Abc 순차' A).
원문 2026000402 (표3)의 특별공급 칸을 읽되, 금액이 도시근로자 2025 × % 와 1원 단위로 같은 유형만 받는다 (정답: tests/golden/notices.json 2026000402)."""
import re
from pathlib import Path

from app import notice_pdf

ROOT = Path(__file__).resolve().parents[1]
T = re.sub(r"\s+", " ", (ROOT / "evidence/notices/2026000402.txt").read_text(encoding="utf-8"))


def test_reads_consistent_types_only():
    pl = notice_pdf.parse_pub_limits((ROOT / "evidence/notices/2026000402.txt").read_text(encoding="utf-8"))
    assert set(pl["sp"]) == {"multichild", "elder", "first", "newborn"}
    assert pl["sp_unread"] == ["newlywed"]   # 신혼부부 일반·추첨 칸 3인 이상 금액이 다른 해 기준 → 판정하지 않음
    assert "2" not in pl["sp"]["multichild"]["amt"]   # 다자녀 2인 칸은 '-'
    assert pl["sp"]["elder"]["amt"]["2"][0] == [7626151, 8212778] and pl["sp"]["elder"]["pct2"][1] == [130, 200]
    assert pl["sp"]["newborn"]["tiers"] == [["우선공급", 70, 100, 120], ["일반공급", 20, 140, 150], ["추첨공급", 10, 140, 200]]
    assert pl["relax"] == {"real_estate": [23705, 25860], "car": [4996, 5451]}


def test_one_wrong_amount_drops_that_type():
    i = T.find("(표3) 전년도 도시근로자")
    bad = T[i:].replace("9,386,032", "9,386,099", 1)   # (표3) 안 첫 자리 = 신생아 일반공급 맞벌이 150% 2인 금액을 67원 틀리게
    sp, unread = notice_pdf._pub_table_sp(bad)
    assert "newborn" not in sp and "newborn" in unread
    sp2, _ = notice_pdf._pub_table_sp(T[i:].replace("추첨공급(10%)", "추첨공급(15%)", 1))   # 다자녀 비율 합 105
    assert "multichild" not in sp2


def test_other_notices_have_no_pub_table_sp():
    for g in sorted((ROOT / "evidence/notices").glob("*.txt")):
        if g.stem == "2026000402":
            continue
        pl = notice_pdf.parse_pub_limits(g.read_text(encoding="utf-8")) or {}
        assert "sp_unread" not in pl and (pl.get("kind") != "pub_table"), g.stem


def test_asset_limits_survive_spacing_changes():
    """'45,420천원이하'(띄어쓰기 없음)여도 기본 칸을 읽고, 출산가구 완화 줄(49,960 54,510 45,420)의 첫 칸을 기본 기준으로 잡지 않는다
    (2026-10-10: 다시 받은 2026000402 글에서 자동차 기준이 4,996만으로 읽혀 기준보다 비싼 차도 통과)"""
    t = ("구분 자산보유기준 부동산 (건물+토지) 215,500천원이하 건축물 … 자동차 45,420천원이하 • 보건복지부장관 … "
         "부동산(건물+토지) 237,050천원 이하 258,600천원 이하 215,500천원 이하 <표2> 참고 자동차 49,960천원 이하 54,510천원 이하 45,420천원 이하 "
         "(표3) 전년도 도시근로자 가구원수별 가구당 월평균소득 기준")
    pl_text = notice_pdf.re.sub(r"(천원|만원)\s?이하", r"\1 이하", t)
    m_re = next(m for m in notice_pdf.re.finditer(r"부동산\s*\(건물\s*\+\s*토지\)\s*([\d,]+)천원 이하(?! ?[\d,]{6,}천원 이하)", pl_text))
    m_car = next(m for m in notice_pdf.re.finditer(r"자동차\s*([\d,]+)천원 이하(?! ?[\d,]{5,}천원 이하)", pl_text))
    assert (m_re.group(1), m_car.group(1)) == ("215,500", "45,420")
    for rev in ("f7cdc478", None):   # 예전 글·지금 글 모두
        import subprocess
        txt = subprocess.run(["git", "show", f"{rev}:evidence/notices/2026000402.txt"], capture_output=True, text=True, cwd=ROOT).stdout if rev else (ROOT / "evidence/notices/2026000402.txt").read_text(encoding="utf-8")
        if not txt:
            continue
        pl = notice_pdf.parse_pub_limits(txt)
        assert (pl["real_estate"], pl["car"]) == (21550, 4542), rev


def test_crosscheck_flags_collected_asset_limit_off_base():
    from app import crosscheck
    from app.models import Listing
    L = Listing(id="2026000402-059.9288A", name="익산 부송에코르", address="전북 익산시", region="지방", kind="공공임대", category="general", unit="59A", price=0.72,
                apply="2026-10-21", notice="2026-10-08", url="https://x", pub_limits={"kind": "pub_table", "real_estate": 21550, "car": 4996})
    facts = {"2026000402": {"asset_thousand": {"부동산": [215500, 237050, 258600], "자동차": [45420, 49960, 54510]}}}
    log = crosscheck.run([L], facts)
    assert any("수집한 자동차 기준 49,960천원" in x for x in log) and any("자동차" in c for c in L.checks)


def test_parse_snapshot_counts_value_changes_when_text_changes():
    from tools.qa.parse_snapshot import moved_diffs
    old = {"1": {"sha": "a", "parse": {"residence": {"months": 0}, "quotes": {"x": "1"}}}, "2": {"sha": "b", "parse": {"car": 4542}}}
    new = {"1": {"sha": "A", "parse": {"quotes": {"x": "2"}}}, "2": {"sha": "b", "parse": {"car": 4996}}}
    mv = moved_diffs(old, new)
    assert len(mv) == 1 and mv[0].startswith("1 residence")
    q_only = moved_diffs({"3": {"sha": "a", "parse": {"complex": {"households": 1859, "quote": "총 1,859세대"}}}},
                         {"3": {"sha": "B", "parse": {"complex": {"households": 1859, "quote": "총 1,859 세대"}}}})
    assert q_only == []   # 값 안의 근거 문장만 다르면 세지 않음 (2026-10-11 거짓 경보)   # 글이 바뀐 1번만(값 사라짐), 글이 같은 2번은 테스트(diff)가 따로 본다, 근거 문장 차이는 세지 않음
