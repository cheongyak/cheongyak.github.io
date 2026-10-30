"""공고문 원문 ↔ 앱 예치금 기준 대조 — 머리글 칸에 괄호 지역 이름이 붙은 예치금 표 (2026-10-31 아침 자동 고치기).
2026000523 형곡 센트럴 아테라(구미, 10-30 공고) 원문 예치금 표:
  '구 분 특별시 및 광역시를 제외한 지역(구미시 및 경상북도) 그 밖의 광역시(대구광역시) 특별시 및 부산광역시'
  '전용면적 85㎡ 이하 200만원 250만원 300만원' … '모든면적 500만원 1,000만원 1,500만원'
머리글의 마지막 '구'를 '구미시'에서 찾아 앞 칸을 잘라 먹고 순서를 추정(서울·부산 먼저)해 '공고문 200만원 ≠ 앱 300만원' 거짓 불일치가 났다."""
from app.crosscheck import app_constants, notice_problems
from app.notice_pdf import notice_facts

HEAD = "■ 청약예금 예치금액\n구 분 특별시 및 광역시를 제외한 지역(구미시 및 경상북도) 그 밖의 광역시(대구광역시) 특별시 및 부산광역시\n"
ROWS = ("전용면적 85㎡ 이하 200만원 250만원 300만원\n전용면적 102㎡ 이하 300만원 400만원 600만원\n"
        "전용면적 135㎡ 이하 400만원 700만원 1,000만원\n모든면적 500만원 1,000만원 1,500만원\n")


def test_deposit_header_with_region_names_in_brackets():
    dep = notice_facts(HEAD + ROWS)["deposit_rows"]
    assert dep["85"] == {"other": 200, "metro": 250, "seoul_busan": 300}
    assert dep["all"] == {"other": 500, "metro": 1000, "seoul_busan": 1500}
    assert not any(r.get("order_guess") for r in dep.values())
    assert [p for p in notice_problems(notice_facts(HEAD + ROWS), app_constants()) if "예치금" in p] == []


def test_deposit_header_still_guesses_without_header_and_flags_wrong_numbers():
    # 머리글이 없으면 지금처럼 순서를 추정했다고 표시한다
    dep = notice_facts("■ 예치금\n" + ROWS)["deposit_rows"]
    assert all(r.get("order_guess") for r in dep.values())
    # 머리글을 읽어도 숫자가 법령 표와 다르면 불일치로 잡는다
    bad = ROWS.replace("200만원 250만원 300만원", "200만원 250만원 350만원")
    assert any("예치금" in p for p in notice_problems(notice_facts(HEAD + bad), app_constants()))
