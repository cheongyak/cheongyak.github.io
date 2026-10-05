"""LH 임대 데이터 불변식 (기능 lh_rental, 일반분양 tools/qa/invariants.py 와 같은 역할) → evidence/qa/lh-invariants.json

docs/lh-rental.json 을 검사한다. 걸린 것은 '[검증·LH]' 줄로 출력(수집 기록에 남김), 정답 데이터와 다르면 '[검증·LH 정답 불일치]'.
 - 일정: 접수 시작 ≤ 접수 끝 ≤ 서류 대상 발표 ≤ 당첨자 발표 (있는 값끼리)
 - 임대조건: 보증금 100만~5억 원, 월 임대료 1만~300만 원, 보증금 > 월 임대료
 - 자격: 판정 유형인데 계층을 못 읽음 / 소득 % 50~250 / 총자산 5천만~6억(만원 5,000~60,000) / 자동차 0~1억 / 1인·2인·3인 이상 % 순서(1인 ≥ 2인 ≥ 3인 이상)
 - 소득 100% 표(도시근로자) ↔ 앱 고정값 URBAN_2025
 - 정답 데이터(tests/golden/lh_rental.json)에 있는 공고는 읽은 값이 정답과 같아야 함(못 읽은 값은 허용 — 화면은 '공고문 확인')
실행: python -m tools.qa.lh_invariants  (종료 코드: 위반 있으면 1)"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.lh_terms import URBAN_2025  # noqa: E402

KEYS = [("장기종사자", "장기종사자"), ("대학생", "대학생"), ("신혼부부·한부모", "신혼|한부모"), ("청년", "청년"), ("고령자", "고령자"), ("주거급여수급자", "주거급여"), ("일반", "일반")]


def _key(name):
    return next((k for k, p in KEYS if re.search(p, name or "")), name)


def check(data: dict, golden: list) -> dict:
    v = defaultdict(list)
    G = {g["id"]: g for g in golden}
    for N in data.get("notices", []):
        nid = N["id"]
        for s in N.get("schedule") or []:
            seq = [s.get(k) for k in ("apply_start", "apply_end", "docs_target", "winner")]
            seq = [x for x in seq if x]
            if seq != sorted(seq):
                v["schedule_order"].append(f"{nid} {s.get('complex')} {seq}")
        for r in N.get("rents") or []:
            if not (1_000_000 <= r["deposit"] <= 500_000_000):
                v["rent_deposit_range"].append(f"{nid} {r['type']} {r['deposit']}")
            if not (10_000 <= r["rent"] <= 3_000_000):
                v["rent_monthly_range"].append(f"{nid} {r['type']} {r['rent']}")
            if r["deposit"] <= r["rent"]:
                v["rent_order"].append(f"{nid} {r['type']}")
        T = N.get("terms")
        if N.get("judge_type"):
            if not T or not T.get("groups"):
                v["terms_unread"].append(f"{nid} {N.get('type')} {N.get('name', '')[:30]}")
        for g in (T or {}).get("groups", []):
            ip = g.get("income_pct")
            if isinstance(ip, dict):
                vals = [ip.get(k) for k in ("1", "2", "3+")]
                if any(x is not None and not (50 <= x <= 250) for x in vals):
                    v["income_pct_range"].append(f"{nid} {g['key']} {ip}")
                nn = [x for x in vals if x is not None]
                if nn != sorted(nn, reverse=True):
                    v["income_pct_order"].append(f"{nid} {g['key']} {ip}")
            a = g.get("asset_manwon")
            if isinstance(a, int) and not (5_000 <= a <= 60_000):
                v["asset_range"].append(f"{nid} {g['key']} {a}")
            c = g.get("car_manwon")
            if isinstance(c, int) and not (0 <= c <= 10_000):
                v["car_range"].append(f"{nid} {g['key']} {c}")
        if T and T.get("income_basis") == "도시근로자 월평균소득":
            for k, val in (T.get("income_table_100") or {}).items():
                if URBAN_2025.get(int(k)) != val:
                    v["urban_table"].append(f"{nid} {k}인 공고문 {val} ≠ 앱 {URBAN_2025.get(int(k))}")
        g0 = G.get(nid)
        if g0 and T:
            P = {x["key"]: x for x in T.get("groups", [])}
            for gg in g0["groups"]:
                p = P.get(_key(gg["name"]))
                for f in ("homeless", "income_pct", "asset_manwon", "car_manwon"):
                    if gg.get(f) is None or not p or p.get(f) is None:
                        continue
                    if p[f] != gg[f]:
                        v["golden"].append(f"{nid} {gg['name']} {f}: 수집 {p[f]} ≠ 정답 {gg[f]}")
            for f in ("relaxed", "homeless_relaxed", "homeless_max1", "regions", "account"):
                if f in g0 and T.get(f) is not None and T.get(f) != g0[f]:
                    v["golden"].append(f"{nid} {f}: 수집 {T.get(f)} ≠ 정답 {g0[f]}")
            if "local" in g0:
                loc = T.get("local")
                got = loc and {k: loc[k] for k in ("name", "sido", "sigun")}
                if got != (g0["local"] or None):
                    v["golden"].append(f"{nid} local: 수집 {got} ≠ 정답 {g0['local']}")
            gold_pairs = {(r["deposit"], r["rent"]) for r in g0.get("rents") or []}
            for r in N.get("rents") or []:
                if gold_pairs and (r["deposit"], r["rent"]) not in gold_pairs:
                    v["golden"].append(f"{nid} 임대조건 정답에 없는 줄 {r}")
    return {k: {"count": len(x), "examples": x[:10]} for k, x in v.items()}


def main() -> int:
    data = json.loads((ROOT / "docs/lh-rental.json").read_text(encoding="utf-8"))
    golden = json.loads((ROOT / "tests/golden/lh_rental.json").read_text(encoding="utf-8"))["notices"]
    viol = check(data, golden)
    total = sum(x["count"] for x in viol.values())
    kst = timezone(timedelta(hours=9))
    out = {"date": datetime.now(kst).strftime("%Y-%m-%d %H:%M"), "data_updated": data.get("updated"), "notices": len(data.get("notices", [])),
           "violations": viol, "count": total}
    (ROOT / "evidence/qa/lh-invariants.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[검증·LH] 임대 공고 {out['notices']}건 · 불변식 위반 {total}건" + (" · " + ", ".join(f"{k} {x['count']}" for k, x in viol.items()) if viol else ""))
    for k, x in viol.items():
        tag = "[검증·LH 정답 불일치]" if k == "golden" else "[검증·LH]"
        for e in x["examples"]:
            print(f"{tag} {k}: {e}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
