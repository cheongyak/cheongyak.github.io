"""SH 임대 수집 1단계(app/sh_rental.py, 기능 sh_rental) — 목록·첨부 읽기는 실제로 받은 화면(evidence/qa/sh/, 2026-10-06 sh_probe)으로,
접수 기간 읽기는 규칙 시험. 정답 데이터(공고문 원문 확인)는 tests/golden/sh_rental.json."""
import json

import pytest
from pathlib import Path

from app.sh_rental import apply_period, downlist, kind_of, pick_pdf, rows_from, SKIP, WANT

ROOT = Path(__file__).resolve().parents[1]


def test_rows_from_real_list():
    rows = rows_from((ROOT / "evidence/qa/sh/list-app.html").read_text(encoding="utf-8"))
    assert len(rows) == 10
    r = next(x for x in rows if x["seq"] == "310650")
    assert r["date"] == "2026-09-30" and r["title"].startswith("2026년 하반기 신혼·신생아 매입임대주택Ⅰ 입주자 모집공고")


def test_downlist_and_pick_pdf_real_view():
    files = downlist((ROOT / "evidence/qa/sh/view-310650.html").read_text(encoding="utf-8"))
    assert len(files) >= 3
    f = pick_pdf(files)
    assert f["oriFileNm"].startswith("[공고문_신혼1]") and f["oriFileNm"].endswith(".pdf")   # 주택목록(요약) PDF 가 아니라 공고문


def test_kind_and_filter():
    assert kind_of("2026년 하반기 신혼·신생아 매입임대주택Ⅰ 입주자 모집공고(2026.09.30.)") == "신혼·신생아 매입임대"
    assert kind_of("[청년형] 특화형 매입임대주택(금천구) 입주자 모집 공고") == "청년 매입임대"
    assert kind_of("2026년 2차 청년안심주택 입주자 모집공고") == "청년안심주택"
    assert kind_of("제50차 장기전세주택 입주자 모집공고") == "장기전세"
    assert kind_of("[토지지원 사회주택]에어스페이스 신림3호점_어울리 입주자 모집 공고") == "사회주택"
    for t, ok in [("2026년 하반기 신혼·신생아 매입임대주택Ⅰ 입주자 모집공고", True), ("2026년 1차 청년안심주택(2026. 3. 31. 공고) 예비1차 당첨자 발표", False),
                  ("홍은동 청년협동조합(이웃기웃) 잔여세대 입주자 모집공고(2026.06.05.) 최종입주대상자 및 예비자 발표", False), ("장기안심주택 2027년 1월 재계약 대상자 입주자격 심사결과", False)]:
        assert (bool(WANT.search(t)) and not SKIP.search(t)) == ok, t


@pytest.fixture(autouse=True)
def _table_on(monkeypatch):
    """표 일정 읽기(기능 sh_schedule_table)는 켠 상태로 시험 — 끈 상태는 test_schedule_table_off"""
    import app.sh_rental as S
    monkeypatch.setattr(S, "feature_on", lambda n: True)


def test_schedule_table_off(monkeypatch):
    import app.sh_rental as S
    monkeypatch.setattr(S, "feature_on", lambda n: False)
    assert S.apply_period("공고 ▶ 사전 주택공개 ▶ 인터넷 청약접수 ▶ 서류심사 26. 9. 23. (수) 26. 9. 29.(화)~ 9. 30.(수) 26. 10. 6.(화) ~10. 8.(목)", "2026-09-23") is None
    assert S.apply_period("입주 신청서 접수 2026.10.02(금) ~ 2026.10.11(일)", "2026-10-07") is None


def test_apply_period_rules():
    r = apply_period("■ 청약접수 : 2026. 10. 13.(월) ~ 10. 15.(수) 10:00~17:00", "2026-09-30")
    assert (r["apply_start"], r["apply_end"], r["rank1"]) == ("2026-10-13", "2026-10-15", False)
    r = apply_period("공고 ▶ 사전 주택공개 ▶ 인터넷 청약접수 ▶ 서류심사 26. 9. 23. (수) 26. 9. 29.(화)~ 9. 30.(수) 26. 10. 6.(화) ~10. 8.(목)", "2026-09-23")   # 일정표: 단계 차례 = 날짜 차례 (기능 sh_schedule_table)
    assert (r["apply_start"], r["apply_end"], r["from_table"]) == ("2026-10-06", "2026-10-08", True)
    assert apply_period("<우편접수 신청서류> ■ 접수기간 : 2026. 10. 2.(금) ~ 10. 6.(화)", "2026-09-23") is None   # 우편접수 안내
    assert apply_period("청약신청 접수 1순위 '26.9.29.(화) ~26.10.2.(금) 2순위 '26.10.8.(목)", "2026-09-09")["rank1"] is True
    assert apply_period("인터넷 접수기간 2026.10.20 ~ 2026.10.22", "2026-10-01")["apply_end"] == "2026-10-22"
    assert apply_period("신청접수 2026년 12월 29일 ~ 1월 2일", "2026-12-10")["apply_end"] == "2027-01-02"   # 해를 넘김
    assert apply_period("접수기간 2025.10.13 ~ 2025.10.15", "2026-09-30") is None   # 등록일보다 한참 전 (지난 공고 인용)
    assert apply_period("신청접수 2026.10.13 ~ 2026.12.31", "2026-09-30") is None    # 60일 넘는 범위는 접수 기간으로 보지 않음
    assert apply_period("모집 세대 10세대", "2026-09-30") is None


def test_golden_sh():
    """정답 데이터(사람이 공고문 원문으로 확인한 접수 기간)와 저장된 공고문 글에서 읽은 값이 같아야 한다."""
    gp = ROOT / "tests/golden/sh_rental.json"
    if not gp.exists():
        return
    for g in json.loads(gp.read_text(encoding="utf-8"))["notices"]:
        t = (ROOT / "evidence/sh" / f"{g['seq']}.txt").read_text(encoding="utf-8")
        got = apply_period(t, g["posted"])
        got = got and {k: got[k] for k in ("apply_start", "apply_end")}
        if g["expect_read"]:
            assert got == g["apply"], (g["seq"], got)
        else:
            assert got is None or got == g["apply"], (g["seq"], got)   # 읽지 않거나, 읽으면 맞아야 함 (틀린 날짜 금지)
        assert kind_of(g["title"]) == g["type"], g["seq"]


def test_schedule_table_rules():
    """표 일정 읽기 (기능 sh_schedule_table, 2026-10-08) — 확실할 때만"""
    # 접수 단계가 첫째: 첫 날짜 묶음
    r = apply_period("모집일정 입주신청기간 ⇨ 계약 대상자 발표 ⇨ 주택 열람 ⇨ 계약체결 26.09.28.(월) ~ 26.10.05.(월) 접수마감 26.10.06.(화) 개별 통보", "2026-09-28")
    assert (r["apply_start"], r["apply_end"]) == ("2026-09-28", "2026-10-05")
    # 우편 접수 단계는 접수로 보지 않음
    assert apply_period("공고 ▶ 우편접수 ▶ 서류심사 발표 26. 9. 23. (수) 26. 10. 2.(금) ~ 10. 6.(화) 26. 10. 19.(월)", "2026-09-23") is None
    # 날짜 묶음이 단계 차례만큼 없으면 안 읽음
    assert apply_period("공고 ▶ 사전 주택공개 ▶ 인터넷 청약접수 ▶ 서류심사 26. 9. 23. (수) 추후 안내", "2026-09-23") is None
    # 날짜 차례가 거꾸로면(표를 잘못 짝지음) 안 읽음
    assert apply_period("공고 ▶ 주택공개 ▶ 청약접수 ▶ 발표 26. 10. 20. (화) 26. 9. 29.(화)~ 9. 30.(수) 26. 10. 6.(화) ~10. 8.(목)", "2026-09-23") is None
    # 게시판에 늦게 올린 공고: 등록일에 아직 접수 중이면 인정, 이미 끝났으면 아님
    assert apply_period("입주 신청서 접수 2026.10.02(금) ~ 2026.10.11(일)", "2026-10-07")["apply_end"] == "2026-10-11"
    assert apply_period("입주 신청서 접수 2026.09.02(수) ~ 2026.09.11(금)", "2026-10-07") is None
