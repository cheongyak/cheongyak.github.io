"""특별공급 판정(docs/index.html, 기능 special_eligibility)에 넣은 기준값이 모집공고문 원문에 실제로 있는지 검사한다.
원문: evidence/notices (Actions 가 청약홈·LH 공고문 PDF 에서 뽑아 저장한 텍스트). 표가 줄바꿈으로 쪼개져 있어 공백을 지우고 찾는다."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
N = ROOT / "evidence" / "notices"
HTML = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")


def text(no: str) -> str:
    p = N / f"{no}.txt"
    if not p.exists():
        pytest.skip(f"{no} 원문 없음")
    return re.sub(r"\s+", "", p.read_text(encoding="utf-8"))


def squeeze(s: str) -> str:
    return re.sub(r"\s+", "", s)


def test_income_table_2025_matches_notice():
    # 더샵 분당하이스트(2026000103) 신혼부부 소득기준 표 100% 행: 3인 이하·4·5·6·7·8인
    t = text("2026000103")
    m = re.search(r"const SP_INCOME_2025 = \[([\d, ]+)\]", HTML)
    vals = [int(x) for x in m.group(1).split(",")]
    for v in vals:
        assert f"~{v:,}원" in t, v
    assert "2025년도도시근로자가구원수별가구당월평균소득기준" in t
    assert "1인당평균소득(579,278)" in t and "SP_PER_PERSON = 579278" in HTML


def test_percent_amounts_round_like_notice():
    # 130%·160% 금액이 공고문 신생아 표와 같게 반올림되는지 (3인 이하, 4인)
    t = text("2026000103")
    base = [7533763, 8802202]
    for b, pct in ((base[0], 130), (base[1], 130), (base[0], 160), (base[1], 160)):
        assert f"{round(b * pct / 100):,}원" in t


def test_minyoung_rules_quoted():
    t = text("2026000443")   # 비규제 민영 (부산)
    assert squeeze("①소득구분 → ②지역 → ③추첨") in t
    assert squeeze("우선공급 (50%) 세대의 월평균소득이 전년도 도시근로자 가구원수별 월평균소득의 130% 이하") in t
    assert squeeze("일반공급 (20%) 세대의 월평균소득이 전년도 도시근로자 가구원수별 월평균소득의 130% 초과 160% 이하") in t
    assert squeeze("160% 초과하나, 부동산가액 3억 3,100만원 이하") in t
    assert "SP_ASSET = { minyoung: 33100" in HTML
    assert squeeze("노부모부양 특별공급 : 무주택세대주 요건") in t
    t = text("2026000103")   # 규제 민영 (성남 분당)
    assert squeeze("부부 모두 소득이 있는 경우 120% 이하, 단 부부 중 1인의 소득은 100% 이하") in t
    assert squeeze("혼인기간이 7년 이내") in t
    assert squeeze("만 19세 미만의 자녀 2명 이상") in t
    assert squeeze("만 65세 이상의 직계존속(배우자의 직계존속 포함)을 3년 이상 계속하여 부양") in t
    assert squeeze("2세 미만(2세가 되는 날을 포함한다)의 자녀(임신중이거나 입양한 경우 포함)") in t
    assert squeeze("5년 이상 소득세를 납부") in t
    t = text("2026000453")   # 규제 민영 (광명): 생애최초·신생아도 세대주
    assert squeeze("노부모부양 / 생애최초 / 신생아 특별공급: 무주택세대주 요건") in t


def test_public_rules_quoted():
    t = text("2026000409")   # LH 의정부우정 A2
    assert squeeze("140%(본인 및 배우자가 모두 소득이 있는 경우 200%) 이하") in t          # 신생아
    assert squeeze("130%(본인 및 배우자가 모두 소득이 있는 경우 200%) 이하") in t          # 신혼부부·생애최초
    assert squeeze("120%(본인 및 배우자가 모두 소득이 있는 경우 200%) 이하") in t          # 다자녀·노부모
    assert "215,500천원" in t and "45,420천원" in t
    assert "SP_ASSET = { minyoung: 33100, public: 21550, car: 4542 }" in HTML
    assert squeeze("1인 가구의 경우 생애최초 특별공급 청약신청이 불가") in t
    assert squeeze("600만원 이상") in t
