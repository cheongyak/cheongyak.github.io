"""지난 공고 1년치 보관 기준 (tools/history/window.py, 2026-10-02 사용자: '과거 공고는 1년치로만 운영')."""
from tools.history import window as W


def test_cutoff_never_before_start():
    assert W.cutoff("2026-10-02") == "2026-01-01"          # 아직 1년이 안 됨 — 2026-01-01 부터 전부
    assert W.cutoff("2027-03-01") == "2026-03-01"


def test_in_window_boundary():
    today = "2027-03-01"
    assert W.in_window({"apply": "2026-02-20", "apply_end": "2026-03-01"}, today)        # 마감일 = 기준일 → 남김
    assert not W.in_window({"apply": "2026-02-20", "apply_end": "2026-02-28"}, today)    # 하루 전 마감 → 지움
    assert W.in_window({"apply": "2026-02-28"}, today) is False                          # 접수 끝이 없으면 접수 시작으로
    assert W.in_window({"apply": "2027-03-10"}, today)                                   # 마감 전
    assert W.in_window({}, today)                                                        # 날짜 모름 → 지우지 않음


def test_fetch_since_covers_notice_before_close():
    assert W.fetch_since("2027-03-01") == "2026-01-01"           # 2025-12-31 이지만 보관 시작 전이라
    assert W.fetch_since("2027-06-01") == "2026-04-02"
