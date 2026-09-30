from app import lawd as LW


class R:
    def __init__(self, code, js): self.status_code, self._js = code, js
    def json(self): return self._js


class H:
    def __init__(self, r): self.r = r
    def get(self, *a, **k): return self.r


def gc(code, a1, a2, a3=""):
    return {"results": [{"code": {"id": code}, "region": {"area1": {"name": a1}, "area2": {"name": a2}, "area3": {"name": a3}}}]}


def test_key_and_table():
    assert LW.key_of("경상남도 진주시 충무공동 1") == "경남 진주시"
    assert LW.lawd_for("서울특별시 강동구 천호동 1", {}) == "11740"
    assert LW.lawd_for("경상남도 진주시 충무공동 1", {}) is None
    assert LW.lawd_for("경상남도 진주시 충무공동 1", {"경남 진주시": {"code": "48170"}}) == "48170"


def test_reverse_ok_and_match():
    info, msg = LW.reverse(35.1, 128.1, H(R(200, gc("4817012300", "경상남도", "진주시", "충무공동"))), ("a", "b"))
    assert info["code"] == "48170" and msg == "ok"
    assert LW.matches("경상남도 진주시 충무공동 1", info)
    assert not LW.matches("경상남도 사천시 사남면 1", info)


def test_reverse_forbidden():
    info, msg = LW.reverse(35.1, 128.1, H(R(403, {})), ("a", "b"))
    assert info is None and "Reverse Geocoding" in msg


def test_new_merged_city_and_paren_address():
    # 2026-07-01 출범 전남광주통합특별시: 시·도 표에 없어 청약홈 공급지역 이름을 쓴다
    a = "전남광주통합특별시 북구 임동 100-1 일원"
    assert LW.key_of(a, "광주") == "광주 북구"
    info = {"code": "29170", "names": "전남광주통합특별시 북구 임동"}
    assert LW.matches(a, info)
    assert not LW.matches(a, {"code": "26290", "names": "부산광역시 북구 구포동"})
    # 행정 주소가 괄호 안에 있는 공고
    b = "광주연구개발특구 첨단3지구 A6블록(전남광주통합특별시 북구 월출동) "
    assert LW.RG.main_address(b) == "전남광주통합특별시 북구 월출동"
    assert LW.key_of(b, "광주") == "광주 북구"
    assert LW.lawd_for(b, {"광주 북구": {"code": "29170"}}, "광주") == "29170"


def test_geo_query_from_paren_address():
    from app.geo import address_queries
    q = address_queries("광주연구개발특구 첨단3지구 A6블록(전남광주통합특별시 북구 월출동) ")
    assert q and q[0][0] == "전남광주통합특별시 북구 월출동"
    assert address_queries("서울특별시 강동구 천호동 1-1")[0][0] == "서울특별시 강동구 천호동 1-1"
