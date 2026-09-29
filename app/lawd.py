"""실거래가 조회용 시군구 코드(LAWD_CD, 법정동코드 앞 5자리).

서울·경기·인천은 app/rules.py 표를 쓰고, 그 밖 지역은 네이버 역지오코딩(법정동 코드)으로 한 번 구해
docs/lawd-cache.json 에 쌓는다 (키: '시도 시군구', 예: '경남 진주시'). 코드를 추측해서 만들지 않는다.
역지오코딩 결과의 시·도·시군구 이름이 공고 주소와 다르면 버린다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import httpx

from . import region as RG

CACHE = Path(__file__).resolve().parent.parent / "docs" / "lawd-cache.json"
REVERSE_URL = "https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc"


def key_of(address: str) -> Optional[str]:
    sido = RG.sido_of(address)
    if not sido:
        return None
    sg = RG.sigungu_any(address)
    return f"{sido} {sg}" if sg else (sido if sido == "세종" else None)


def load(path: Path = None) -> dict:
    try:
        return json.loads((path or CACHE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(cache: dict, path: Path = None) -> None:
    (path or CACHE).write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def lawd_for(address: str, cache: Optional[dict] = None) -> Optional[str]:
    """표에 있으면 표, 없으면 역지오코딩으로 모아 둔 기록."""
    code = RG.lawd_of(RG.sigungu_of(address))
    if code:
        return code
    k = key_of(address)
    e = (cache if cache is not None else load()).get(k) if k else None
    return e.get("code") if isinstance(e, dict) else None


def reverse(lat: float, lng: float, http: httpx.Client, key: tuple[str, str]) -> tuple[Optional[dict], str]:
    r = http.get(REVERSE_URL, params={"coords": f"{lng},{lat}", "orders": "legalcode", "output": "json"},
                 headers={"x-ncp-apigw-api-key-id": key[0], "x-ncp-apigw-api-key": key[1]})
    if r.status_code != 200:
        return None, f"역지오코딩 응답 {r.status_code}" + (" (네이버 클라우드 앱에서 Reverse Geocoding 사용 설정 필요)" if r.status_code in (401, 403) else "")
    res = (r.json().get("results") or [{}])[0]
    code = str((res.get("code") or {}).get("id") or "")
    reg = res.get("region") or {}
    names = [(reg.get(f"area{i}") or {}).get("name", "") for i in (1, 2, 3)]
    if len(code) < 5 or not code[:5].isdigit():
        return None, f"코드 없음 ({' '.join(names)})"
    return {"code": code[:5], "legal_code": code, "names": " ".join(n for n in names if n)}, "ok"


def matches(address: str, info: dict) -> bool:
    """역지오코딩 지역 이름이 공고 주소의 시·도·시군구와 같은지."""
    names = info.get("names", "")
    sido = RG.sido_of(address)
    if not sido or RG.sido_of(names) != sido:
        return False
    sg = RG.sigungu_any(address)
    return sg is None or sg.split(" ")[0] in names
