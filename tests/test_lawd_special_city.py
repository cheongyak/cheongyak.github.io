"""특례시 주소·화성시 일반구 (2026-10-03 사용자 제보: 향남역 그로브 스위첸 '시군구 코드를 확인하지 못해 시세를 조회하지 못했어요').
근거: evidence/qa/lawd-probe.txt — 옛 화성시 코드 41590 은 2026-02 이후 매매 0건, 41591(만세구)은 향남읍 거래가 달마다 20~36건.
네이버 지오코딩은 '화성특례시 만세구'를 0건, '화성시 만세구'를 1건(역지오코딩 41591 '경기도 화성시 만세구 향남읍')으로 찾음."""
from app import geo, lawd, region as RG

HN = "경기도 화성특례시 만세구 향남읍 하길리 404-2번지 일원"


def test_hwaseong_manse_code():
    assert RG.sigungu_of(HN) == "화성시 만세구"
    assert lawd.lawd_for(HN, {}) == "41591"


def test_geocode_query_uses_legal_city_name():
    assert geo.address_queries(HN)[0][0] == "경기도 화성시 만세구 향남읍 하길리 404-2"


def test_other_special_cities_still_map():
    assert RG.lawd_of(RG.sigungu_of("경기도 수원특례시 영통구 이의동 1")) == "41117"
    assert RG.lawd_of(RG.sigungu_of("경기도 고양특례시 일산동구 장항동 1")) == "41285"
    assert RG.lawd_of(RG.sigungu_of("경기도 용인특례시 수지구 1")) == "41465"


def test_unverified_hwaseong_gu_not_guessed():
    """확인 안 한 구는 표에 코드를 넣지 않는다 → 지도 좌표 역지오코딩으로 구함. 옛 코드 41590 은 쓰지 않는다."""
    assert lawd.lawd_for("경기도 화성시 동탄구 오산동 1", {}) is None
    assert lawd.lawd_for("경기도 화성시 봉담읍 1", {}) is None
    assert lawd.key_of("경기도 화성특례시 동탄구 오산동 1") == "경기 화성시 동탄구"
    assert lawd.matches(HN, {"names": "경기도 화성시 만세구 향남읍"})


def test_bucheon_gu_codes():
    """부천시는 2024-01 원미구·소사구·오정구로 나뉨. 옛 코드 41190 은 최근 12개월 매매·분양권·전월세 0건, 원미구 41192 는 매매 4,448건(상동 1,373)
    (evidence/qa/market-probe.txt 2026-10-07, 상동역 롯데캐슬 시그니처 역지오코딩 41192 '경기도 부천시 원미구 상동').
    소사구·오정구는 실제 조회로 확인하지 않아 표에 두지 않고 역지오코딩 기록을 쓴다."""
    A = "경기도 부천시 원미구 상동 540-1번지"
    assert RG.sigungu_of(A) == "부천시 원미구" and lawd.lawd_for(A, {}) == "41192"
    assert lawd.lawd_for("경기도 부천시 소사구 괴안동 1", {}) is None
    assert lawd.lawd_for("경기도 부천시 소사구 괴안동 1", {"경기 부천시 소사구": {"code": "41194"}}) == "41194"
    assert lawd.lawd_for("경기도 부천시 상동 1", {}) is None   # 구가 없는 주소는 옛 코드(41190, 0건)를 쓰지 않고 역지오코딩으로
    assert "41190" not in RG.R.GYEONGGI_LAWD.values()
