"""가까운 곳부터 시세 비교(기능 market_nearby) 미리 보기 — 스위치를 켜기 전에 '켜면 무엇이 바뀌나'를 지금 공고 전체로 계산한다.

지금 화면 데이터(docs/listings.json, 같은 구 기준)는 그대로 두고, 같은 실거래가로 app/market_nearby 를 돌려 공고마다
  기존 시세·등급 → 새 시세·등급, 쓴 단계(같은 동·반경 1/1.5/2km·같은 구 그대로), 거래 수, 단계별 건수
를 evidence/qa/market-nearby.json 에 적는다. 단지 좌표는 evidence/market/complex-geo.json 에 저장(수집이 다시 씀).
실거래가·지도 키가 필요해 Actions('가까운 곳 시세 미리 보기' market-nearby.yml, 손으로 실행)에서만 돈다.
사용: python -m tools.qa.market_nearby_report [--only 2026910275,2026000513]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "evidence" / "qa" / "market-nearby.json"
CASES = ("2026910275", "2026000513", "2026000514", "2026000508", "2026000509")   # 운영자가 짚은 사례 (분당하이스트·트리븐센텀·아크메르 동탄)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    if not os.environ.get("DATA_GO_KR_KEY"):
        print("[가까운 곳 시세] 인증키 없음 — 건너뜀 (Actions 에서만 돈다)")
        return 0
    from app import engine, lawd as LC, market_nearby as MN
    from app import rules as R
    from app.market import months_back
    from app.models import Listing
    from app.sources import rtms
    today = datetime.now(timezone(timedelta(hours=9))).date()
    data = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    rows = data["listings"] if isinstance(data, dict) else data
    rows = [r for r in rows if not r.get("sample") and (not a.only or r["id"].split("-")[0] in a.only.split(","))]
    Ls = [Listing.model_validate(r) for r in rows]
    lawd_cache = LC.load()
    months = months_back(today, R.MARKET_MONTHS)
    targets = [L for L in Ls if MN.RULE.get(L.mkt_basis or "") and not L.rental]
    lawds = sorted({LC.lawd_for(L.address, lawd_cache, L.sido) for L in targets} - {None})
    rt = rtms.RtmsClient()
    keys = [("trade", l, ym) for l in lawds for ym in months]
    pf = rt.prefetch(keys, budget_sec=600, workers=3)   # 10-28 첫 실행: 8개 동시에 받다 429(요청 과다) 48건 → 그 구 공고가 빠짐. 3개씩 + 못 받은 것 다시
    for _ in range(3):
        left = [k for k in keys if k not in rt._cache]
        if not left:
            break
        import time
        time.sleep(20)
        rt.frozen = False
        p2 = rt.prefetch(left, budget_sec=300, workers=2)
        pf = {**pf, "retry": pf.get("retry", []) + [p2]}
    missing = sorted({k[1] for k in keys if k not in rt._cache})
    pf["missing_lawd"] = missing
    before = {L.id: (L.mkt_basis, L.mkt_low, L.mkt_base, L.mkt_count, L.mkt_note, engine.grade(L)) for L in Ls}
    log: list[str] = []
    MN.apply(Ls, rt, today, lawd_cache, log, save=True)
    coords = MN.usable(MN.load_coords(), today)
    items, changes, fixtures = [], [], []
    for L in Ls:
        b = before[L.id]
        g = engine.grade(L)
        it = {"id": L.id, "name": L.name, "unit": L.unit, "area": L.area, "price": L.price, "address": L.address,
              "geo_precision": (L.geo or {}).get("precision"),
              "old": {"basis": b[0], "low": b[1], "base": b[2], "count": b[3], "note": b[4], "grade": b[5]["name"], "lo": b[5]["lo"], "rate": b[5]["rate"]},
              "new": {"basis": L.mkt_basis, "low": L.mkt_low, "base": L.mkt_base, "count": L.mkt_count, "note": L.mkt_note, "grade": g["name"],
                      "lo": g["lo"], "rate": g["rate"]}}
        if MN.RULE.get(b[0] or "") and not L.rental:
            lawd = LC.lawd_for(L.address, lawd_cache, L.sido)
            try:
                tr = rt.recent("trade", lawd, months) if lawd else []
            except Exception:
                it["steps"] = [("실거래 못 받음", lawd)]
                items.append(it)
                continue
            _, info = MN.estimate_nearby(L.address, L.area, b[0], tr, today.year, L.geo, coords, lawd or "")
            it["steps"] = info["steps"]
            it["no_coord"] = info.get("no_coord")
            if L.id.split("-")[0] in CASES:   # 회귀 시험 고정본(tests/qa/market_nearby_cases.json)으로 옮길 원자료: 이 규칙의 같은 구 후보 거래 + 단지 좌표
                pool = MN.rule_pool(tr, L.area, MN.RULE[b[0]], today.year)
                ks = {MN.complex_key(lawd, r) for r in pool} - {None}
                fixtures.append({"id": L.id, "address": L.address, "area": L.area, "basis": b[0], "geo": L.geo, "lawd": lawd, "year": today.year,
                                 "old": {"low": b[1], "base": b[2], "count": b[3]},
                                 "trades": [{k: r.get(k) for k in ("apt", "umd", "jibun", "area", "amount", "build_year", "deal_type", "date", "floor")} for r in pool],
                                 "coords": {k: coords[k] for k in sorted(ks) if k in coords}})
        if L.id.split("-")[0] in CASES or b[5]["name"] != g["name"]:
            it["comps"] = L.mkt_comps
        if b[5]["name"] != g["name"]:
            changes.append({"id": L.id, "name": L.name, "unit": L.unit, "old": b[5]["name"], "new": g["name"],
                            "old_mkt": f"{b[1]}~{b[2]}억 {b[3]}건 ({b[0]})", "new_mkt": f"{L.mkt_low}~{L.mkt_base}억 {L.mkt_count}건 ({L.mkt_basis})",
                            "price": L.price, "why": L.mkt_note})
        items.append(it)
    out = {"generated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "prefetch": pf, "log": log,
           "fields": sorted(rtms.SEEN_FIELDS), "targets": len(targets), "grade_changes": changes,
           "cases": [it for it in items if it["id"].split("-")[0] in CASES], "items": items}
    (OUT.parent / "market-nearby-cases.json").write_text(json.dumps(fixtures, ensure_ascii=False, indent=0, default=str) + "\n", encoding="utf-8")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print("\n".join(log))
    print(f"[가까운 곳 시세] 대상 {len(targets)} · 등급 바뀜 {len(changes)} · 실거래 칸 {', '.join(sorted(rtms.SEEN_FIELDS))}")
    for c in changes:
        print(f"  {c['id']} {c['name']}: {c['old']} → {c['new']} · {c['old_mkt']} → {c['new_mkt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
