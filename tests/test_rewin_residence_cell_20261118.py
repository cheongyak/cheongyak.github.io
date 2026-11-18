"""재당첨 제한 — 1쪽 표 거주요건 칸의 'N년 이상 거주자' 숫자를 잡지 않기 (2026-11-18 밤 자동 개선).

근거: evidence/audit/2026-11-16-blind/README.md 앱 오류 P1 — 2026820015 시흥 거모 아테라(A-6BL) 신혼희망타운 본청약.
저장 원문 evidence/notices/2026820015.txt
  40·41줄 '주택유형 규제지역여부 거주요건 재당첨제한 / 공공분양(신혼희망타운) 비규제지역 수도권 거주자 (경쟁시 시흥시 1년 이상 거주자 우선) 10년'
  154줄  '분양가상한제 적용주택으로 「주택공급에 관한 규칙」제54조에 따라 재당첨제한은 10년 적용되고'
  157줄  '재당첨제한 당첨자 발표일 10년 「공공주택 특별법」…'
고치기 전에는 일반 규칙이 거주요건 칸의 '1년'을 먼저 잡아 화면이 '재당첨 제한 1년'으로 안내했다.
"""
from pathlib import Path

from app.notice_pdf import parse_notice

ROOT = Path(__file__).resolve().parents[1]

TABLE = ("단 지 주 요 정 보\n주택유형 규제지역여부 거주요건 재당첨제한\n"
         "공공분양(신혼희망타운) 비규제지역 수도권 거주자 (경쟁시 시흥시 1년 이상 거주자 우선) 10년\n"
         "전매제한 거주의무기간 분양가상한제 택지유형\n3년 없음 적용 공공택지\n")


def test_stored_notice_2026820015_rewin_10():
    r = parse_notice((ROOT / "evidence/notices/2026820015.txt").read_text(encoding="utf-8"))
    assert r["rewin_years"] == 10
    assert "10년" in r["quotes"]["rewin_years"]


def test_body_sentence_beats_residence_cell():
    t = TABLE + "■ 과밀억제권역의 분양가상한제 적용주택으로 「주택공급에 관한 규칙」제54조에 따라 재당첨제한은 10년 적용되고, 전매제한이 3년 적용됩니다.\n"
    assert parse_notice(t)["rewin_years"] == 10


def test_restriction_table_row_beats_residence_cell():
    t = TABLE + "구분 기준일(~로부터) 기간 관련 법령\n재당첨제한 당첨자 발표일 10년 「공공주택 특별법」\n"
    assert parse_notice(t)["rewin_years"] == 10


def test_sentence_about_other_house_is_not_this_notice():
    # '…5년 적용되는 주택에 당첨된 분' 은 과거 당첨 주택 설명 — 이 공고의 기간(표 10년)이 아니다
    t = ("■ 과거 재당첨제한이 5년 적용되는 주택에 당첨된 분은 그 기간 안에 청약할 수 없습니다.\n"
         "구분 기준일(~로부터) 기간 관련 법령\n재당첨제한 당첨자 발표일 10년 「공공주택 특별법」\n")
    assert parse_notice(t)["rewin_years"] == 10
    for other in ("과거 재당첨제한이 5년 적용된 주택에 당첨된 분", "재당첨제한이 3년 적용받는 주택", "재당첨제한이 5년 적용대상인 주택"):
        t2 = "■ " + other + "은 청약할 수 없습니다.\n재당첨제한 당첨자 발표일 10년 「공공주택 특별법」\n"
        assert parse_notice(t2)["rewin_years"] == 10, other
    assert parse_notice("재당첨제한은 10년 적용된다.\n")["rewin_years"] == 10


def test_first_page_table_rule_still_first():
    # 1쪽 표가 '재당첨제한 전매제한 거주의무기간 분양가상한제' 한 줄 꼴이면 그 규칙이 그대로 먼저 (청계 노르웨이숲 2026910263 꼴)
    t = "재당첨제한 전매제한 거주의무기간 분양가상한제 택지유형\n없음 최초당첨자발표일로부터 3년\n재당첨제한은 10년 적용되는 주택\n"
    assert parse_notice(t)["rewin_years"] == 0
