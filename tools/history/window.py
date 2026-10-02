"""지난 공고 보관 기간 (기능: historical_search·historical_judge, 2026-10-02 사용자: '과거 공고는 1년치로만 운영').
마감일(접수 끝, 없으면 접수 시작)이 오늘로부터 KEEP_DAYS 일 이내인 공고만 남기고, 그보다 오래된 공고는 보관함·판정 자료·공고문 기록에서 지운다.
보관 시작은 2026-01-01 (그 전 공고는 처음부터 넣지 않음)."""
from datetime import date, timedelta

KEEP_DAYS = 365
START = "2026-01-01"


def cutoff(today: str) -> str:
    """이 날짜보다 먼저 마감된 공고는 지운다."""
    return max(START, (date.fromisoformat(today) - timedelta(days=KEEP_DAYS)).isoformat())


def fetch_since(today: str) -> str:
    """청약홈에 공고일 기준으로 물을 시작일. 공고 뒤 마감까지 길게는 두 달쯤이라 60일 앞당겨 묻고, 남길지는 마감일로 가린다."""
    return max(START, (date.fromisoformat(cutoff(today)) - timedelta(days=60)).isoformat())


def close_date(r: dict) -> str | None:
    return r.get("apply_end") or r.get("apply")


def in_window(r: dict, today: str) -> bool:
    """마감 전이거나 마감일이 cutoff 이후면 남긴다. 날짜를 모르면 공고일로 본다(그것도 없으면 남김)."""
    d = close_date(r) or r.get("notice")
    return not d or d >= cutoff(today)
