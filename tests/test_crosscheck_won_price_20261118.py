"""공고문 대조 — 원 단위 공급금액이 만원 아래까지 있는 표 (2026-11-18 운영자 '확인중으로 뜨는데 왜').

잠실 래미안아이파크 불법행위 재공급(2026930045): 공급금액 표 합계 '1,105,484,366'(대지비+건축비+재분양비, 원)를 청약홈은 110,548만원으로 준다.
대조 도구가 '1,105,480'(만원 아래 0) 꼴만 찾아 43·59A 를 '공고문에 없음'으로 잘못 잡았다(84D '1,856,070,144' 는 앞자리가 우연히 맞아 통과).
"""
from pathlib import Path

from app import notice_pdf as N

T = (Path(__file__).resolve().parent.parent / "evidence/notices/2026930045.txt").read_text(encoding="utf-8")


def test_won_table_with_sub_manwon_digits():
    f = N.notice_facts(T, {"043.7300": 110548, "059.4700A": 157939, "084.9600D": 185607})
    assert f["price_seen"] == {"043.7300": True, "059.4700A": True, "084.9600D": True}


def test_wrong_price_still_flagged():
    # 만원 단위가 하나라도 다르면 여전히 잡는다
    f = N.notice_facts(T, {"043.7300": 110549, "059.4700A": 157938})
    assert f["price_seen"] == {"043.7300": False, "059.4700A": False}
