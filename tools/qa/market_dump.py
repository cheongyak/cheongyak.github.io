"""시세 근거 거래 전부 보기 (운영자 질문 '이 공고 왜 비추천이야?' 2026-10-31 광교 자연앤 센트레빌).
화면에는 근거 거래가 최근 8건만 나와서, 시세(보수=하위 25%, 기준=중앙값)를 만든 거래 전부를 단지·거리와 함께 적는다.
같은 시군구 6개월 매매 중 같은 평형(±3㎡)·준공 10년 이내·직거래 뺀 것 (app/market·market_nearby 와 같은 조건), 가격순.
실거래가 키가 필요해 Actions('가까운 곳 시세 미리 보기' market-nearby.yml 의 dump 입력)에서만 돈다.
사용: python -m tools.qa.market_dump 2026000528-084.7637A → evidence/qa/market-dump.json"""
from __future__ import annotations

import json
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "evidence" / "qa" / "market-dump.json"


def main() -> int:
    ids = [x for x in (sys.argv[1:] or []) if x]
    if not ids or not os.environ.get("DATA_GO_KR_KEY"):
        print("[시세 근거 전부] 공고 id 또는 인증키 없음 — 건너뜀")
        return 0
    from app import lawd as LC, market_nearby as MN, rules as R
    from app.market import _in_band, dong_of, months_back
    from app.sources import rtms
    today = datetime.now(timezone(timedelta(hours=9))).date()
    data = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    rows = data["listings"] if isinstance(data, dict) else data
    coords = MN.load_coords()
    lawd_cache = LC.load()
    rt = rtms.RtmsClient()
    out = {"generated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "items": []}
    for pid in ids:
        L = next((r for r in rows if r["id"].strip().startswith(pid)), None)
        if not L:
            out["items"].append({"id": pid, "error": "공고 없음"})
            continue
        lawd = LC.lawd_for(L["address"], lawd_cache, L.get("sido"))
        tr = rt.recent("trade", lawd, months_back(today, R.MARKET_MONTHS))
        g = L.get("geo") or {}
        pool = []
        for r in tr:
            if r.get("deal_type") == "직거래" or not r.get("amount") or not _in_band(r.get("area"), L["area"]):
                continue
            if not (r.get("build_year") and r["build_year"] >= today.year - R.NEW_BUILD_YEARS):
                continue
            c = coords.get(MN.complex_key(lawd, r) or "", {})
            m = MN.dist_m(g["lat"], g["lng"], c["lat"], c["lng"]) if "lat" in c and g.get("lat") else None
            pool.append({"apt": r["apt"], "umd": r["umd"], "build": r["build_year"], "area": r["area"], "floor": r.get("floor"),
                         "amount": round(r["amount"] / 10000, 2), "date": r["date"], "m": m})
        pool.sort(key=lambda x: x["amount"])
        dong = dong_of(L["address"])
        mine = [p for p in pool if p["umd"].split()[:1] == [dong] and (p["m"] is None or p["m"] <= max(R.NEARBY_RADII))]
        by = {}
        for p in mine:
            by.setdefault((p["apt"], p["build"], p["m"]), []).append(p["amount"])
        out["items"].append({"id": L["id"], "name": L["name"], "price": L["price"], "mkt": [L.get("mkt_low"), L.get("mkt_base"), L.get("mkt_count"), L.get("mkt_basis")],
                             "dong": dong, "pool_district": len(pool), "pool_dong_2km": len(mine),
                             "by_complex": sorted(([k[0], k[1], k[2], len(v), min(v), statistics.median(v), max(v)] for k, v in by.items()), key=lambda x: x[5]),
                             "trades": mine})
        print(f"[시세 근거 전부] {L['id']} {L['name']}: 같은 동 2km 안 {len(mine)}건 (구 전체 {len(pool)}건)")
        for k in sorted(by.items(), key=lambda kv: statistics.median(kv[1])):
            print(f"   {k[0][0]} ({k[0][1]:.0f}년 준공, {k[0][2]}m) {len(k[1])}건 · {min(k[1])}~{max(k[1])}억 (중앙 {statistics.median(k[1])})")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
