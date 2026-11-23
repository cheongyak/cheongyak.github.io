"""같은 단지 두 공고의 시세·판정이 갈린 일 (2026-11-24 운영자 데이터 확인 요청).

2026930048 동탄신도시 금강펜테리움 7차 센트럴파크 불법행위재공급 — 주소 '경기도 화성시 신동 동탄2택지개발지구(A57-2블럭)'라 동 중심(37.18278, 127.141696)에서
반경 1.5km 를 재서 시세 6.48~6.88억 → 마진없음. 같은 단지 2026910303(2차 무순위)은 도로명 '동탄신리천로8길 17'로 정확한 위치
(37.174323, 127.142107 = '신동 820 동탄신도시 금강펜테리움7차 센트럴파크')에서 재서 5.0~5.4억 → 비추천. 두 공고 모두 모집공고문 총 662세대, 84A 5.532억.
값은 2026-11-24 docs/listings.json 에서 옮김.
"""
from types import SimpleNamespace as NS

from app.geo import borrow_sibling_geo, complex_name_key

DONG = {"lat": 37.18278, "lng": 127.141696, "precision": "dong", "query": "경기도 화성시 신동", "matched": "경기도 화성시 동탄구 신동",
        "source": "네이버 클라우드 플랫폼 Geocoding"}
EXACT = {"lat": 37.174323, "lng": 127.142107, "precision": "exact", "query": "경기도 화성시 동탄구 동탄신리천로8길 17",
         "matched": "경기도 화성시 동탄구 신동 820 동탄신도시 금강펜테리움7차 센트럴파크", "source": "네이버 클라우드 플랫폼 Geocoding"}


def L(name, address, hh=662, sido="경기"):
    return NS(name=name, address=address, sido=sido, complex={"households": hh})


def _case(a_hh=662, b_name="동탄신도시 금강펜테리움 7차 센트럴파크(2차)", dong=DONG):
    groups = {"2026930048": [L("동탄신도시 금강펜테리움 7차 센트럴파크 불법행위재공급", "경기도 화성시 신동 동탄2택지개발지구(A57-2블럭)", a_hh)],
              "2026910303": [L(b_name, "경기도 화성시 동탄구 동탄신리천로8길 17, 동탄신도시 금강펜테리움 7차 센트럴파크")]}
    found = {"2026930048": (dict(dong) if dong else None, None), "2026910303": (dict(EXACT), [{"name": "역", "m": 900}])}
    log = []
    n = borrow_sibling_geo(groups, found, log)
    return n, found, log


def test_dong_only_notice_uses_same_complex_exact_location():
    n, found, log = _case()
    geo, nb = found["2026930048"]
    assert n == 1
    assert (geo["lat"], geo["lng"], geo["precision"]) == (EXACT["lat"], EXACT["lng"], "exact")
    assert geo["via"] == {"notice": "2026910303", "address": "경기도 화성시 동탄구 동탄신리천로8길 17, 동탄신도시 금강펜테리움 7차 센트럴파크",
                          "own": "경기도 화성시 신동"}
    assert nb == [{"name": "역", "m": 900}]                    # 주변 입지도 정확한 위치 것
    assert found["2026910303"][0] == EXACT                       # 빌려 준 쪽은 그대로
    assert any("같은 단지 공고 2026910303" in s for s in log)


def test_no_coordinates_at_all_also_borrows():
    n, found, _ = _case(dong=None)
    assert n == 1 and found["2026930048"][0]["lat"] == EXACT["lat"]


def test_not_same_complex_when_households_differ():
    n, found, _ = _case(a_hh=500)
    assert n == 0 and found["2026930048"][0]["precision"] == "dong"


def test_not_same_complex_when_name_differs():
    n, found, _ = _case(b_name="동탄신도시 금강펜테리움 6차 센트럴파크(2차)")   # '7차' 같은 단지 이름의 차수는 지우지 않는다
    assert n == 0


def test_too_far_from_dong_center_is_not_borrowed():
    far = dict(DONG, lat=DONG["lat"] + 0.04)   # 약 4.4km 북쪽
    n, found, log = _case(dong=far)
    assert n == 0 and found["2026930048"][0]["precision"] == "dong"
    assert any("넘게 떨어져" in s for s in log)


def test_complex_name_key():
    a = complex_name_key("동탄신도시 금강펜테리움 7차 센트럴파크 불법행위재공급")
    assert a == complex_name_key("동탄신도시 금강펜테리움 7차 센트럴파크(2차)") == "동탄신도시금강펜테리움7차센트럴파크"
    assert complex_name_key("이천 서희스타힐스 SKY (조합원 취소분)") == "이천서희스타힐스SKY"
    assert complex_name_key("남양주왕숙 A-2블록 신혼희망타운(공공분양) 잔여세대 추가입주자모집공고") == "남양주왕숙A-2블록신혼희망타운(공공분양)".replace("(", "").replace(")", "")
