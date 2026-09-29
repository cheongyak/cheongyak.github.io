"""공고 위치(좌표)와 주변 입지.

- 좌표: 네이버 클라우드 플랫폼(NCP) Maps Geocoding. 키는 GitHub Secrets
  NCP_MAPS_CLIENT_ID / NCP_MAPS_CLIENT_SECRET 에만 둔다. 키가 없으면 이 단계는 건너뛴다.
  분양 주소는 '○○동 일원 (○○지구 A-4블록)'처럼 지번이 없는 경우가 많아
  (1) 지번·도로명까지 (2) 동·읍·면까지 순서로 찾고, 어느 쪽으로 찾았는지(precision)를 남긴다.
  못 찾으면 좌표를 만들지 않는다 (추측 좌표 금지).
- 주변 입지: OpenStreetMap(Overpass API)의 역·학교 위치로 공고 좌표에서의 직선거리를 잰다.
  도보 시간은 직선거리 × 1.3 ÷ 분당 67m 로 계산한 추정치다.
- 한 번 구한 값은 지난 실행 결과(docs/listings.json)에서 재사용한다 (주소가 같을 때).
"""
from __future__ import annotations

import math
import os
import re
import time
from typing import Optional

import httpx

from . import region as RG

GEOCODE_URL = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
OVERPASS_URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
                 "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
GEO_SOURCE = "네이버 클라우드 플랫폼 Geocoding"
NEARBY_SOURCE = "OpenStreetMap"
STATION_RADIUS_M = 2000
SCHOOL_RADIUS_M = 1500
GEO_BUDGET_SEC = 240      # 주변 입지 조회에 쓰는 최대 시간
KOREA = (33.0, 39.0, 124.0, 132.0)   # 위도 최소·최대, 경도 최소·최대


def keys() -> Optional[tuple[str, str]]:
    cid, sec = os.environ.get("NCP_MAPS_CLIENT_ID"), os.environ.get("NCP_MAPS_CLIENT_SECRET")
    return (cid, sec) if cid and sec else None


_LOT = re.compile(r"산?\d+(?:-\d+)?(?:번지)?")
_STOP = re.compile(r"^(일원|일대|외|및)$|블록$|BL$|지구$|단지$|[A-Za-z]+\d")
_ADMIN_END = re.compile(r"(동|읍|면|리|\d가)$")


def address_queries(address: str) -> list[tuple[str, str]]:
    """공고 주소 → [(검색어, 정밀도)] (정확한 것부터)."""
    s = re.sub(r"\([^)]*\)", " ", address or "")
    s = s.split(" 및 ")[0].split(",")[0]
    area: list[str] = []
    lot = None
    for t in s.split():
        if _LOT.fullmatch(t):
            if area:
                lot = t.replace("번지", "")
            break
        if _STOP.search(t):
            break
        area.append(t)
    out = []
    if lot:
        out.append((" ".join(area + [lot]), "exact"))
    last = max((i for i, t in enumerate(area) if _ADMIN_END.search(t)), default=None)
    if last is not None and last >= 1:
        q = " ".join(area[: last + 1])
        if not out or out[0][0] != q:
            out.append((q, "dong"))
    return out


def in_korea(lat: float, lng: float) -> bool:
    return KOREA[0] <= lat <= KOREA[1] and KOREA[2] <= lng <= KOREA[3]


def geocode(address: str, sido: Optional[str], http: httpx.Client, key: tuple[str, str]) -> tuple[Optional[dict], str]:
    """(좌표 dict 또는 None, 기록 메시지)."""
    tried = []
    for q, precision in address_queries(address):
        r = http.get(GEOCODE_URL, params={"query": q},
                     headers={"x-ncp-apigw-api-key-id": key[0], "x-ncp-apigw-api-key": key[1], "Accept": "application/json"})
        if r.status_code != 200:
            return None, f"Geocoding 응답 {r.status_code}: {r.text[:120]}"
        body = r.json()
        addrs = body.get("addresses") or []
        tried.append(f"'{q}' {len(addrs)}건")
        if not addrs:
            continue
        a = addrs[0]
        lat, lng = float(a["y"]), float(a["x"])
        found = a.get("jibunAddress") or a.get("roadAddress") or ""
        if not in_korea(lat, lng):
            tried.append("국내 범위 밖이라 버림")
            continue
        if sido and RG.sido_of(found) and RG.sido_of(found) != sido:
            tried.append(f"시·도가 달라 버림 ({found})")
            continue
        return ({"lat": round(lat, 6), "lng": round(lng, 6), "precision": precision, "query": q,
                 "matched": found, "source": GEO_SOURCE}, " · ".join(tried))
    return None, " · ".join(tried) or "검색어를 만들지 못했어요"


def _dist_m(lat1, lng1, lat2, lng2) -> int:
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lng2 - lng1) * p / 2) ** 2)
    return int(round(12742000 * math.asin(math.sqrt(a))))


def walk_min(m: int) -> int:
    return max(1, round(m * 1.3 / 67))


def overpass_query(lat: float, lng: float) -> str:
    c = f"{lat},{lng}"
    return (f"[out:json][timeout:25];("
            f'node["railway"="station"](around:{STATION_RADIUS_M},{c});'
            f'node["public_transport"="station"]["subway"="yes"](around:{STATION_RADIUS_M},{c});'
            f'nwr["amenity"="school"](around:{SCHOOL_RADIUS_M},{c});'
            f");out center tags;")


SCHOOL_KINDS = ("초등학교", "중학교", "고등학교")


def parse_nearby(elements: list[dict], lat: float, lng: float) -> list[dict]:
    """Overpass 결과 → 가까운 역(최대 2곳)과 초·중·고 각각 가장 가까운 한 곳."""
    stations: dict[str, dict] = {}
    schools: dict[str, dict] = {}
    for e in elements:
        t = e.get("tags") or {}
        name = (t.get("name:ko") or t.get("name") or "").strip()
        y = e.get("lat", (e.get("center") or {}).get("lat"))
        x = e.get("lon", (e.get("center") or {}).get("lon"))
        if not name or y is None or x is None:
            continue
        d = _dist_m(lat, lng, float(y), float(x))
        if t.get("amenity") == "school":
            kind = next((k for k in SCHOOL_KINDS if name.endswith(k)), None)
            if kind and d <= SCHOOL_RADIUS_M and (kind not in schools or d < schools[kind]["m"]):
                schools[kind] = {"kind": kind, "name": name, "m": d, "lat": float(y), "lng": float(x)}
            continue
        if t.get("railway") == "station" or t.get("public_transport") == "station":
            if t.get("station") in ("funicular", "monorail") or t.get("usage") == "freight":
                continue
            label = name if name.endswith("역") else name + "역"
            key = re.sub(r"\s+", "", label)
            if d <= STATION_RADIUS_M and (key not in stations or d < stations[key]["m"]):
                stations[key] = {"kind": "역", "name": label, "m": d, "lat": float(y), "lng": float(x)}
    near = sorted(stations.values(), key=lambda s: s["m"])[:2]
    near += [schools[k] for k in SCHOOL_KINDS if k in schools]
    for n in near:
        n["walk"] = walk_min(n["m"])
    return near


def nearby(lat: float, lng: float, http: httpx.Client) -> tuple[Optional[list[dict]], str]:
    q = overpass_query(lat, lng)
    errs = []
    for url in OVERPASS_URLS:
        host = url.split("/")[2]
        try:
            r = http.post(url, data={"data": q}, timeout=60)
            if r.status_code == 200:
                return parse_nearby(r.json().get("elements") or [], lat, lng), host
            errs.append(f"{host} 응답 {r.status_code}")
        except Exception as e:
            errs.append(f"{host} {e.__class__.__name__}")
    return None, ", ".join(errs)


def apply_geo(listings: list, log: list[str], previous: Optional[dict] = None, http: Optional[httpx.Client] = None,
              probe: bool = False, geocode_on: bool = True, nearby_on: bool = True) -> None:
    """공고(주소)별로 한 번 좌표와 주변 입지를 구해 같은 공고의 주택형 전체에 넣는다."""
    previous = previous or {}
    prev_by_notice: dict[str, dict] = {}
    for pid, p in previous.items():
        prev_by_notice.setdefault(pid.split("-")[0], p)
    groups: dict[str, list] = {}
    for L in listings:
        groups.setdefault(L.id.split("-")[0], []).append(L)
    key = keys()
    client = http or httpx.Client(timeout=20, headers={"User-Agent": "cheongyak.github.io (daily collector)"})
    start = time.monotonic()
    stat = {"exact": 0, "dong": 0, "none": 0, "reused": 0, "nearby": 0}
    found: dict[str, tuple] = {}
    # 1) 좌표: 빠르므로 모든 공고를 먼저 처리한다
    for nid, Ls in groups.items():
        L0 = Ls[0]
        prev = prev_by_notice.get(nid)
        geo = nb = None
        if prev and prev.get("address") == L0.address and prev.get("geo"):
            geo, nb = prev["geo"], prev.get("nearby")
            stat["reused"] += 1
        elif key and geocode_on:
            try:
                geo, msg = geocode(L0.address, L0.sido, client, key)
            except Exception as e:
                geo, msg = None, f"오류 {e.__class__.__name__}"
            log.append(f"[위치] {L0.name}: {'찾음 (' + geo['precision'] + ') ' + geo['matched'] if geo else '못 찾음'} ← {msg}")
        found[nid] = (geo, nb)
    geo_sec = time.monotonic() - start
    # 2) 주변 입지: 공용 서버라 느릴 수 있어 시간 제한 안에서만. 못 한 공고는 다음 실행에서 다시 시도한다
    for nid, (geo, nb) in found.items():
        if nearby_on and geo and nb is None and time.monotonic() - start < GEO_BUDGET_SEC:
            nb, msg = nearby(geo["lat"], geo["lng"], client)
            log.append(f"[입지] {groups[nid][0].name}: " + (", ".join(f"{n['name']} {n['m']}m" for n in nb) or "반경 안에 역·학교 없음"
                                                          if nb is not None else f"조회 실패 ({msg})"))
            found[nid] = (geo, nb)
            time.sleep(1)   # Overpass 공용 서버 예의
    for nid, Ls in groups.items():
        geo, nb = found[nid]
        stat[geo["precision"] if geo else "none"] += 1
        stat["nearby"] += nb is not None
        qs = address_queries(Ls[0].address)
        for L in Ls:
            L.geo, L.nearby = geo, nb
            L.map_query = qs[0][0] if qs else Ls[0].address
    if not key:
        log.append("[위치] 네이버 지도 키(NCP_MAPS_CLIENT_ID/SECRET)가 없어 새 좌표는 찾지 않았어요")
        if probe and stat["nearby"] == 0:
            # 키가 들어오기 전에 역·학교 조회가 동작하는지 점검 (서울 광진구 구의동 부근 고정 좌표, 데이터에는 넣지 않음)
            try:
                nb, msg = nearby(37.5402, 127.0858, client)
                log.append("[입지·점검] " + (", ".join(f"{n['name']} {n['m']}m" for n in nb) if nb else f"결과 없음 ({msg})"))
            except Exception as e:
                log.append(f"[입지·점검] 실패: {e.__class__.__name__}")
    log.append(f"[위치] 공고 {len(groups)}건: 정확 {stat['exact']} · 동 기준 {stat['dong']} · 못 찾음 {stat['none']}"
               f" (지난 값 재사용 {stat['reused']}) · 주변 입지 {stat['nearby']}건 · 좌표 {geo_sec:.0f}초, 전체 {time.monotonic() - start:.0f}초")
