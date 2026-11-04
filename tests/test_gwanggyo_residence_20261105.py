"""대규모 택지 3단 배정 문장이 PDF 에서 뒤섞인 꼴 (2026000527·528 광교 자연앤 센트레빌, 2026-11-05).

주간 원문 대조(evidence/audit/2026-11-02-blind README 36줄)가 P1 로 남긴 것: 화면이 '수도권 누구나 같은 순위'(equal)로 안내하고
'수원 2년 이상 30% · 경기 2년 이상 20% · 수도권 50%' 배정을 못 보여 줌. 숫자가 낱말 뒤로 밀려 있어 스스로 맞는지 확인한 뒤에만 읽는다.
"""
from app.notice_pdf import parse_residence

S = ("■ 본 아파트는 주택공급에 관한 규칙 제 조 규정에 의거 대규모 택지개발지구에서 공급하는 주택으 로 34 「 」 입주자모집공고일 현재 수원시 년 이상 계속 거주자 (2026.10.30.) 2 (2024.10.30. \n"
     "이전부터 계속 거주 에게 를 우선공급 ) 30% 하며, 경기도 년 이상 계속 거주자 이전부터 계속 거주 에게 를 공급 2 (2024.10.30. ) 20% 하며, 를 수도권 거주자 경기도 년 미만 및 서울특별 50% ( 2 \n"
     "시 인천광역시 거주 에게 공급합니다")


def test_reads_three_tiers():
    r = parse_residence(S)
    assert r == {"area": {"name": "수원시", "sigungu": "수원시"}, "months": 24, "since": "2024-10-30",
                 "gyeonggi": {"months": 24, "since": "2024-10-30"}, "quota": {"해당": 30, "경기": 20, "기타": 50},
                 "others": ["서울", "경기", "인천"]}
    assert "equal" not in r   # 예전: equal true(수도권 모두 같은 순위)


def test_refuses_when_years_and_date_disagree():
    """'2년'인데 이전부터 날짜가 공고일 1년 전이면 숫자를 잘못 짝지은 것 — 이 규칙으로 읽지 않는다."""
    bad = S.replace("2 (2024.10.30. \n이전부터", "2 (2025.10.30. \n이전부터")
    r = parse_residence(bad)
    assert not (r and r.get("quota"))


def test_refuses_when_shares_do_not_add_up():
    bad = S.replace(") 20% 하며", ") 25% 하며")
    r = parse_residence(bad)
    assert not (r and r.get("quota"))
