"""공고문 원문 ↔ 앱 자산 기준 대조 (app/notice_pdf.notice_facts asset_thousand → app/crosscheck.notice_problems).
2026-10-09 익산 부송에코르 10년 공공임대(2026000402): 원문에 '부동산 (건물+토지) 215,500천원 이하'가 있는데 줄바꿈과 출산가구 표(첫 칸 237,050)만 읽어
'앱 215,500천원이 공고문에 없음' 거짓 경고 → 사이트 베타 상자가 빨갛게 뜸."""
from pathlib import Path

from app.crosscheck import app_constants, notice_problems
from app.notice_pdf import notice_facts

ROOT = Path(__file__).resolve().parents[1]
T402 = (ROOT / "evidence/notices/2026000402.txt").read_text(encoding="utf-8")


def test_402_reads_base_and_all_birth_columns():
    a = notice_facts(T402)["asset_thousand"]
    assert {215500, 237050, 258600} <= set(a["부동산"]) and {45420, 49960, 54510} <= set(a["자동차"])
    assert notice_problems({"asset_thousand": a}, app_constants()) == []


def test_real_difference_still_flagged():
    a = notice_facts(T402.replace("215,500천원", "216,000천원"))["asset_thousand"]   # 기준이 바뀐 공고문이면
    p = notice_problems({"asset_thousand": a}, app_constants())
    assert any("216,000" in x for x in p) and any("앱 215,500천원이 공고문에 없음" in x for x in p)


def test_neighbouring_rows_not_mixed():
    """부동산 칸 뒤 40자 안의 자동차 금액·총자산 금액을 부동산으로 섞어 읽지 않는다 (넓게 읽었을 때 생긴 거짓 경고)"""
    t = "부동산(건물+토지) 215,500천원 이하 자동차 45,420천원 이하 총자산 362,000천원 이하"
    a = notice_facts(t)["asset_thousand"]
    assert a["부동산"] == [215500] and a["자동차"] == [45420]


def test_deposit_header_with_city_names_inside():
    """예치금 표 머리글 안에 '구미시'·'대구광역시'가 있어도 칸 순서를 머리글로 읽는다 (2026-10-31 형곡 센트럴 아테라 2026000523 원문 그대로).
    전엔 마지막 '구'(대구광역시)부터 머리글로 봐서 순서를 추정 → 서울·부산 칸과 그 밖의 지역 칸이 뒤집혀 공고문 대조 8건이 거짓 불일치"""
    from app.notice_pdf import notice_facts
    t = ("[ 청약예금의 예치금액 ]\n구 분 특별시 및 광역시를 제외한 지역(구미시 및 경상북도) 그 밖의 광역시(대구광역시) 특별시 및 부산광역시\n"
         "전용면적 85㎡ 이하 200만원 250만원 300만원\n전용면적 102㎡ 이하 300만원 400만원 600만원\n"
         "전용면적 135㎡ 이하 400만원 700만원 1,000만원\n모든면적 500만원 1,000만원 1,500만원\n")
    dep = notice_facts(t)["deposit_rows"]
    assert dep["85"] == {"other": 200, "metro": 250, "seoul_busan": 300}
    assert dep["102"] == {"other": 300, "metro": 400, "seoul_busan": 600}
    assert dep["135"] == {"other": 400, "metro": 700, "seoul_busan": 1000}
    assert dep["all"] == {"other": 500, "metro": 1000, "seoul_busan": 1500}
