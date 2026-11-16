"""정적 페이지 조사·금액 범위 글 (2026-11-17 운영자: 애드센스 재심사 직전 점검).

① 이름 끝이 괄호·기호·숫자·로마 숫자여도 '은(는)' 같은 표기가 나오지 않고 은/는 하나로 정해진다 (끝의 괄호 묶음은 빼고 그 앞 글자로 판단)
② 임대보증금·월 임대료 값이 하나면 'A원부터 A원까지'가 아니라 'A원'
"""
import pytest

from tools import seo_pages as sp


@pytest.mark.parametrize("word,eun,ro", [
    ("경남 통영안정 국민임대주택 예비입주자 자격완화 모집('26.11.16.)", "은", "으로"),   # 괄호 앞 '모집'
    ("2026년 3차 희망하우징(공공기숙사) 잔여세대 입주자 모집공고(2026. 10. 28.)", "는", "로"),   # 괄호 앞 '공고'
    ("검단Ⅳ", "는", "로"),            # 로마 숫자 4 = 사
    ("힐스테이트 회룡역파크뷰", "는", "로"),
    ("A1블록", "은", "으로"),
    ("센트럴파크 (2차) ", "는", "로"),
    ("공고 [수정]", "는", "로"),
    ("자이 3", "은", "으로"),            # 삼
    ("자이 1", "은", "로"),              # 일 — ㄹ 받침은 '로'
    ("LH", "는", "로"),                  # 에이치
    ("서울숲 \"포레\"", "는", "로"),
])
def test_josa_picks_one(word, eun, ro):
    assert sp.josa(word, "은", "는") == eun
    assert sp.ro(word) == ro


def test_josa_never_returns_both_forms():
    for w in ["", "()", "㎡", "…", "(가칭)", "84㎡", "A-1", "e편한세상", "2026.01", "단지)"]:
        for a, b in (("은", "는"), ("이", "가"), ("을", "를"), ("이에요", "예요")):
            assert sp.josa(w, a, b) in (a, b)
        assert sp.ro(w) in ("으로", "로")


def test_won_range_single_value():
    assert sp.won_range([6376000]) == "6,376,000원"
    assert sp.won_range([100200, 100200]) == "100,200원"
    assert sp.won_range([100, 300, 200]) == "100원부터 300원까지"


def test_rental_page_single_rent_and_particle():
    n = {"id": "X-1", "name": "시험 국민임대 예비입주자 모집('26.11.16.)", "type": "국민임대", "region": "경상남도", "posted": "2026-11-16", "close": "2026-12-03",
         "schedule": [{"apply_start": "2026-11-30", "apply_end": "2026-12-03"}], "units": [{"type": "29A", "area": 29.57, "households": 214}],
         "rents": [{"type": "29", "group": None, "deposit": 6376000, "rent": 100200}]}
    body = sp.rental_page("lh", n)[2]
    assert "임대보증금은 6,376,000원, 월 임대료는 100,200원예요" not in body and "임대보증금은 6,376,000원, 월 임대료는 100,200원이에요(모집공고문)" in body
    assert "부터 6,376,000원까지" not in body and "은(는)" not in body
    assert "</b>은 경상남도에서" in body
    n2 = dict(n, rents=n["rents"] + [{"type": "46", "group": None, "deposit": 9000000, "rent": 150000}])
    assert "임대보증금은 6,376,000원부터 9,000,000원까지, 월 임대료는 100,200원부터 150,000원까지예요(모집공고문)" in sp.rental_page("lh", n2)[2]
