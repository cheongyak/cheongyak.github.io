import json

import httpx

from app import geo
from app.models import Listing


def test_address_queries_from_real_notice_addresses():
    q = geo.address_queries
    assert q("서울특별시 광진구 구의동 592-39번지 일원") == [("서울특별시 광진구 구의동 592-39", "exact"), ("서울특별시 광진구 구의동", "dong")]
    assert q("경기도 시흥시 하중동 일원 (시흥하중 공공주택지구 내 A-4블록)") == [("경기도 시흥시 하중동", "dong")]
    assert q("경기도 광명시 소하동 광명 구름산지구 도시개발사업지구 A6BL") == [("경기도 광명시 소하동", "dong")]
    assert q("충청남도 천안시 동남구 풍세로 801(용곡동 617번지)") == [("충청남도 천안시 동남구 풍세로 801", "exact")]
    assert q("전북특별자치도 전주시 완산구 삼천동1가 585-4번지 일원")[0] == ("전북특별자치도 전주시 완산구 삼천동1가 585-4", "exact")
    assert q("인천광역시 계양구 귤현동, 동양동, 박촌동 및 경기도 부천시 대장동 일원 인천계양 테크노밸리 공공주택지구 내 A6블록") == [("인천광역시 계양구 귤현동", "dong")]
    assert q("부산광역시 강서구 강동동 5048-5번지 일원 에코델타시티 공동6BL")[0] == ("부산광역시 강서구 강동동 5048-5", "exact")


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_geocode_falls_back_to_dong_and_rejects_other_sido():
    calls = []

    def h(req):
        qv = req.url.params["query"]
        calls.append(qv)
        assert req.headers["x-ncp-apigw-api-key-id"] == "id"
        if qv.endswith("592-39"):
            # 다른 시·도가 먼저 나오면 버린다
            return httpx.Response(200, json={"addresses": [{"x": "129.0", "y": "35.1", "jibunAddress": "부산광역시 강서구 구의동"}]})
        return httpx.Response(200, json={"addresses": [{"x": "127.0857", "y": "37.5410", "jibunAddress": "서울특별시 광진구 구의동"}]})

    g, msg = geo.geocode("서울특별시 광진구 구의동 592-39번지 일원", "서울", _client(h), ("id", "sec"))
    assert g["precision"] == "dong" and g["lat"] == 37.541 and g["source"] == geo.GEO_SOURCE
    assert "시·도가 달라 버림" in msg and len(calls) == 2


def test_geocode_none_when_nothing_found():
    g, msg = geo.geocode("경기도 시흥시 하중동 일원", "경기", _client(lambda r: httpx.Response(200, json={"addresses": []})), ("i", "s"))
    assert g is None and "0건" in msg


def test_parse_nearby_groups_lines_and_picks_nearest_school():
    lat, lng = 37.3670, 127.1080
    els = [
        {"type": "node", "lat": 37.3668, "lon": 127.1085, "tags": {"railway": "station", "name": "정자", "station": "subway"}},
        {"type": "node", "lat": 37.3669, "lon": 127.1084, "tags": {"railway": "station", "name": "정자역"}},   # 다른 노선 같은 역
        {"type": "node", "lat": 37.3850, "lon": 127.1230, "tags": {"railway": "station", "name": "서현역"}},
        {"type": "way", "center": {"lat": 37.3700, "lon": 127.1100}, "tags": {"amenity": "school", "name": "신기초등학교"}},
        {"type": "way", "center": {"lat": 37.3800, "lon": 127.1100}, "tags": {"amenity": "school", "name": "먼초등학교"}},
        {"type": "node", "lat": 37.3680, "lon": 127.1090, "tags": {"amenity": "school", "name": "어느 학원"}},
        {"type": "node", "lat": 37.3690, "lon": 127.1070, "tags": {"railway": "station", "name": "화물역", "usage": "freight"}},
    ]
    n = geo.parse_nearby(els, lat, lng)
    names = [x["name"] for x in n]
    assert names[0] == "정자역" and names.count("정자역") == 1
    assert "신기초등학교" in names and "먼초등학교" not in names and "화물역" not in names
    st = n[0]
    assert st["m"] < 100 and st["walk"] >= 1


def _L(i, address="서울특별시 광진구 구의동 592-39번지 일원"):
    return Listing(id=f"{i}-084.0000A", name="테스트", address=address, region="서울", sido="서울", kind="k", unit="84A",
                   area=84, price=10, category="general")


def test_apply_geo_reuses_previous_and_skips_without_key(monkeypatch):
    monkeypatch.delenv("NCP_MAPS_CLIENT_ID", raising=False)
    prev_geo = {"lat": 37.54, "lng": 127.08, "precision": "exact", "query": "q", "matched": "m", "source": geo.GEO_SOURCE}
    prev = {"100-084.0000A": {"address": "서울특별시 광진구 구의동 592-39번지 일원", "geo": prev_geo, "nearby": []}}
    a, b = _L(100), _L(200)
    log = []
    geo.apply_geo([a, b], log, previous=prev, http=_client(lambda r: httpx.Response(500)))
    assert a.geo == prev_geo and a.nearby == []
    assert b.geo is None and b.nearby is None
    assert b.map_query == "서울특별시 광진구 구의동 592-39"
    assert any("키" in l for l in log) and any("재사용 1" in l for l in log)


def test_apply_geo_calls_geocode_and_overpass(monkeypatch):
    monkeypatch.setenv("NCP_MAPS_CLIENT_ID", "id")
    monkeypatch.setenv("NCP_MAPS_CLIENT_SECRET", "sec")
    monkeypatch.setattr(geo.time, "sleep", lambda s: None)

    def h(req):
        if "geocode" in str(req.url):
            return httpx.Response(200, json={"addresses": [{"x": "127.0857", "y": "37.5410", "jibunAddress": "서울특별시 광진구 구의동 592-39"}]})
        return httpx.Response(200, json={"elements": [{"type": "node", "lat": 37.5385, "lon": 127.0857, "tags": {"railway": "station", "name": "강변"}}]})

    a = _L(300)
    log = []
    geo.apply_geo([a], log, http=_client(h))
    assert a.geo["precision"] == "exact"
    assert a.nearby[0]["name"] == "강변역" and 250 < a.nearby[0]["m"] < 300
    assert any(l.startswith("[입지]") for l in log)


def test_validate_flags_coordinate_outside_korea():
    from datetime import date
    from app.validate import listing_checks
    a = _L(1)
    a.geo = {"lat": 0.0, "lng": 0.0}
    assert "지도 좌표가 국내 범위를 벗어나요" in listing_checks(a, date(2026, 9, 29))
