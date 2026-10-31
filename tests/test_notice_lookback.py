"""청약홈 공고 목록 받는 기간 (2026-10-31: 60일이라 인천계양 A6 2026000414 가 당첨자 발표 뒤 14일 전에 화면에서 빠짐 → 공고 누락 점검 실패)."""
from datetime import date, timedelta

from app import pipeline
from app.sources import applyhome


def test_lookback_longer_than_keep_window():
    # 공고 08-31 · 접수 09-17~10-02 · 당첨자 발표 10-20 이면 11-03 까지 화면에 남아야 한다 → 그날도 공고일이 받는 기간 안
    notice, winner = date(2026, 8, 31), date(2026, 10, 20)
    last_day = winner + timedelta(days=applyhome.KEEP_AFTER_WINNER_DAYS)
    assert (last_day - notice).days <= pipeline.NOTICE_LOOKBACK_DAYS
    assert pipeline.NOTICE_LOOKBACK_DAYS >= 120
