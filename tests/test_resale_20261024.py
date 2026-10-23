"""전매제한 1쪽 표가 뒤섞인 꼴 (2026910271 힐스테이트 레이크 송도 4차(2차), 2026-10-24 아침 자동 고치기).
원문 '최초 당첨자발표일 로부터 년간(22.03.02) 3적용되어 현재 전매제한기간 도과' — 숫자 3이 날짜 뒤로 밀림."""
import re

from app import notice_pdf


def _flat(s):
    return re.sub(r"\s+", "", s)


def test_garbled_passed_reads():
    r = notice_pdf.parse_resale(_flat("재당첨제한 전매제한 거주의무기간 분양가상한제 없음 최초 당첨자발표일 로부터 년간(22.03.02) 3적용되어 현재 전매제한기간 도과 없음 미적용"))
    assert r and r["months"] == 36 and r["base"] == "2022-03-02" and r["passed"] is True


def test_garbled_without_passed_not_read():
    # '도과'까지 이어지지 않으면 숫자가 어디 붙는지 확실하지 않으므로 읽지 않는다
    assert notice_pdf.parse_resale(_flat("최초 당첨자발표일 로부터 년간(22.03.02) 3적용")) is None


def test_garbled_number_run_not_read():
    # 날짜 뒤 숫자가 금액·날짜 조각처럼 이어지면 읽지 않는다
    assert notice_pdf.parse_resale(_flat("최초 당첨자발표일 로부터 년간(22.03.02) 3,000적용되어 현재 전매제한기간 도과")) is None
