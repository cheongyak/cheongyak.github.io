"""한 단지 몫 상한(기능 market_complex_balance) 미리 보기 — 스위치를 켜기 전에 '켜면 무엇이 바뀌나'를 지금 공고 전체로 계산한다 (2026-10-31).

같은 실거래가로 수집과 같은 순서(같은 단지 → 같은 구 규칙 → 가까운 곳)를 상한 끔·켬 두 번 돌려 공고마다
  시세(보수·기준)·등급 끔 → 켬, 상한에 걸린 단지
를 evidence/qa/market-balance.json 에 적는다. 끔 결과가 지금 화면 값(docs/listings.json)과 다르면 same_as_screen=false 로 표시(실거래가가 그새 바뀐 것).
실거래가 키가 필요해 Actions('가까운 곳 시세 미리 보기' market-nearby.yml, 입력 balance=yes, 손으로 실행)에서만 돈다.
사용: python -m tools.qa.market_balance_report [--only 2026000528]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "evidence" / "qa" / "market-balance.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    if not os.environ.get("DATA_GO_KR_KEY"):
        print("[단지 몫 상한] 인증키 없음 — 건너뜀 (Actions 에서만 돈다)")
        return 0
    from app import engine, lawd as LC, market as M, market_nearby as MN
    from app import rules as R
    from app.models import Listing
    from app.pipeline import feature_on
    from app.sources import rtms
    today = datetime.now(timezone(timedelta(hours=9))).date()
    data = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    rows = data["listings"] if isinstance(data, dict) else data
    rows = [r for r in rows if not r.get("sample") and not r.get("rental") and r.get("mkt_basis")
            and (not a.only or r["id"].split("-")[0] in a.only.split(","))]
    Ls = [Listing.model_validate(r) for r in rows]
    cache = LC.load()
    months = M.months_back(today, R.MARKET_MONTHS)
    lawd_of = {L.id: LC.lawd_for(L.address, cache, L.sido) for L in Ls}
    lawds = sorted(set(lawd_of.values()) - {None})
    rt = rtms.RtmsClient()
    keys = [(k, l, ym) for l in lawds for ym in months for k in ("trade", "presale")]
    pf = rt.prefetch(keys, budget_sec=600, workers=3)
    for _ in range(3):
        left = [k for k in keys if k not in rt._cache]
        if not left:
            break
        time.sleep(20)
        rt.frozen = False
        rt.prefetch(left, budget_sec=300, workers=2)
    missing = sorted({k[1] for k in keys if k not in rt._cache})
    coords = MN.usable(MN.load_coords(), today)
    nearby = feature_on("market_nearby")
    items, changes = [], []
    for L in Ls:
        lawd = lawd_of[L.id]
        if not lawd or lawd in missing:
            items.append({"id": L.id, "name": L.name, "skip": "실거래 못 받음"})
            continue
        tr, ps = rt.recent("trade", lawd, months), rt.recent("presale", lawd, months)
        res = {}
        for on in (False, True):
            M.BALANCE = on
            mk = M.estimate_market(L.name, L.area, tr, ps, today.year, area_fallback=feature_on("mkt_area_fallback"),
                                   large_fallback=feature_on("mkt_large_fallback"), unit=L.unit, dong=M.dong_of(L.address))
            X = L.model_copy(update=mk)
            if nearby and MN.RULE.get(X.mkt_basis or ""):
                nb, _ = MN.estimate_nearby(X.address, X.area, X.mkt_basis, tr, today.year, X.geo, coords, lawd)
                if nb:
                    X = X.model_copy(update=nb)
            g = engine.grade(X)
            res[on] = {"basis": X.mkt_basis, "low": X.mkt_low, "base": X.mkt_base, "count": X.mkt_count, "note": X.mkt_note,
                       "grade": g["name"], "lo": g["lo"], "rate": g["rate"]}
        M.BALANCE = False
        it = {"id": L.id, "name": L.name, "unit": L.unit, "price": L.price, "off": res[False], "on": res[True],
              "same_as_screen": (res[False]["low"], res[False]["base"]) == (L.mkt_low, L.mkt_base)}
        items.append(it)
        if res[False]["grade"] != res[True]["grade"] or res[False]["low"] != res[True]["low"]:
            changes.append({"id": L.id, "name": L.name, "unit": L.unit, "price": L.price,
                            "off": f"{res[False]['low']}~{res[False]['base']}억 {res[False]['grade']}",
                            "on": f"{res[True]['low']}~{res[True]['base']}억 {res[True]['grade']}",
                            "grade_changed": res[False]["grade"] != res[True]["grade"], "why": res[True]["note"]})
    out = {"generated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "prefetch": pf, "missing_lawd": missing,
           "checked": sum(1 for i in items if "skip" not in i), "changed": len(changes), "grade_changed": sum(c["grade_changed"] for c in changes),
           "not_same_as_screen": [i["id"] for i in items if i.get("same_as_screen") is False], "changes": changes, "items": items}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"[단지 몫 상한] 주택형 {out['checked']} · 시세 바뀜 {len(changes)} · 등급 바뀜 {out['grade_changed']} · 화면 값과 다른 끔 결과 {len(out['not_same_as_screen'])}")
    for c in changes:
        print(f"  {c['id']} {c['name']} {c['unit']}: {c['off']} → {c['on']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
