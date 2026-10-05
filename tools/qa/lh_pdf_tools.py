"""LH 임대 공고문 읽기 도구별 정확도 (기능 lh_pdf_multi, 일반분양 tools/qa/pdf_audit.py 와 같은 역할) → evidence/qa/lh-pdf-tools.json

정답 데이터(tests/golden/lh_rental.json, 공고문 원문 확인값)가 있는 공고마다 pypdf·pypdfium2·pdfplumber 글을 같은 읽기 규칙(app/lh_terms)으로 읽고,
합친 결과(app/lh_pdf_merge)까지 칸마다 맞음·틀림·못 읽음을 센다. 합친 결과는 틀림 0 이어야 하고(틀린 값으로 판정하지 않음),
맞음은 어느 한 도구보다 적으면 안 된다.
실행: python -m tools.qa.lh_pdf_tools  (종료 코드: 합친 결과에 틀림이 있으면 1)"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.lh_pdf_merge import read_all  # noqa: E402
from app.lh_terms import parse_lh_rents, parse_lh_terms  # noqa: E402

KEYS = [("장기종사자", "장기종사자"), ("대학생", "대학생"), ("신혼부부·한부모", "신혼|한부모"), ("청년", "청년"), ("고령자", "고령자"), ("주거급여수급자", "주거급여"), ("일반", "일반")]
GROUP_FIELDS = ("homeless", "income_pct", "asset_manwon", "car_manwon")
NOTICE_FIELDS = ("relaxed", "homeless_relaxed", "homeless_max1", "regions", "account", "income_table_100", "income_add_per")


def _key(name):
    return next((k for k, p in KEYS if re.search(p, name or "")), name)


def texts_of(nid: str) -> dict:
    P = {"pypdf": ROOT / "evidence/lh" / f"{nid}.txt", "pdfium": ROOT / "evidence/lh/pdfium" / f"{nid}.txt", "plumber": ROOT / "evidence/lh/plumber" / f"{nid}.txt"}
    return {t: p.read_text(encoding="utf-8", errors="replace") for t, p in P.items() if p.exists() and p.stat().st_size >= 500}


def score_terms(T: dict, g: dict, st: dict, where: str, rows: list):
    if not T:
        st["missing"] += 1
        return
    P = {x["key"]: x for x in T.get("groups") or []}
    for gg in g["groups"]:
        p = P.get(_key(gg["name"]))
        for f in GROUP_FIELDS:
            if gg.get(f) is None:
                continue
            v = p and p.get(f)
            if v is None:
                st["missing"] += 1
            elif v == gg[f]:
                st["ok"] += 1
            else:
                st["wrong"] += 1
                rows.append(f"{where} {g['id']} {gg['name']}.{f}: 읽음 {v!r} ≠ 정답 {gg[f]!r}")
    for f in NOTICE_FIELDS:
        if f not in g:
            continue
        v = T.get(f)
        if f == "income_table_100" and v and g.get(f):
            v = {k: x for k, x in v.items() if k in g[f]}
        if v is None:
            st["missing"] += 1
        elif v == g[f]:
            st["ok"] += 1
        else:
            st["wrong"] += 1
            rows.append(f"{where} {g['id']} {f}: 읽음 {v!r} ≠ 정답 {g[f]!r}")
    if "local" in g:
        loc = T.get("local")
        got = loc and {k: loc[k] for k in ("name", "sido", "sigun")}
        if got == (g["local"] or None):
            st["ok"] += 1
        elif got is None:
            st["missing"] += 1
        else:
            st["wrong"] += 1
            rows.append(f"{where} {g['id']} local: 읽음 {got} ≠ 정답 {g['local']}")


def score_rents(R: list, g: dict, st: dict, where: str, rows: list):
    gold = {(x["deposit"], x["rent"]) for x in g.get("rents") or []}
    if not gold:
        return
    got = {(r["deposit"], r["rent"]) for r in R or []}
    st["rent_ok"] += len(gold & got)
    st["rent_missing"] += len(gold - got)
    bad = got - gold
    st["rent_wrong"] += len(bad)
    for b in sorted(bad)[:3]:
        rows.append(f"{where} {g['id']} 임대조건 정답에 없는 줄 {b}")


def main() -> int:
    gold = json.loads((ROOT / "tests/golden/lh_rental.json").read_text(encoding="utf-8"))["notices"]
    units = {n["id"]: n for n in json.loads((ROOT / "tests/qa/lh/rental_units.json").read_text(encoding="utf-8"))}
    blank = lambda: {"ok": 0, "wrong": 0, "missing": 0, "rent_ok": 0, "rent_wrong": 0, "rent_missing": 0, "notices": 0}
    stat = {t: blank() for t in ("pypdf", "pdfium", "plumber", "merged")}
    wrong_rows, merge_notes, conflicts = [], [], []
    for g in gold:
        tx = texts_of(g["id"])
        u = units.get(g["id"]) or {}
        region, types = u.get("region"), u.get("types") or []
        for t, x in tx.items():
            stat[t]["notices"] += 1
            score_terms(parse_lh_terms(x, g["type"], g.get("verified_from", ""), region), g, stat[t], t, wrong_rows)
            score_rents(parse_lh_rents(x, types), g, stat[t], t, wrong_rows)
        if len(tx) >= 1:
            tf = ROOT / "evidence/lh/plumber" / f"{g['id']}.tables.json"
            m = read_all(tx, g["type"], g.get("verified_from", ""), region, types, True, json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else [])
            stat["merged"]["notices"] += 1
            score_terms(m["terms"], g, stat["merged"], "merged", wrong_rows)
            score_rents(m["rents"], g, stat["merged"], "merged", wrong_rows)
            merge_notes += [f"{g['id']} {n}" for n in m["notes"]]
            conflicts += [f"{g['id']} {c}" for c in m["conflicts"]]
    # 지금 공고 전체: 도구별로 글을 읽은 공고 수 (정답 데이터가 없는 공고 포함)
    allN = json.loads((ROOT / "docs/lh-rental.json").read_text(encoding="utf-8")).get("notices", [])
    coverage = {t: sum(1 for n in allN if t in texts_of(n["id"])) for t in ("pypdf", "pdfium", "plumber")}
    coverage["notices"] = len(allN)
    kst = timezone(timedelta(hours=9))
    out = {"date": datetime.now(kst).strftime("%Y-%m-%d %H:%M"), "golden_notices": len(gold), "stat": stat,
           "merged_wrong": stat["merged"]["wrong"] + stat["merged"]["rent_wrong"], "coverage": coverage, "wrong": wrong_rows[:80], "merge_notes": merge_notes[:80], "conflicts": conflicts[:80]}
    (ROOT / "evidence/qa/lh-pdf-tools.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for t, s in stat.items():
        print(f"[LH 읽기 도구] {t:8s} 공고 {s['notices']:2d} · 자격 칸 맞음 {s['ok']} 틀림 {s['wrong']} 못 읽음 {s['missing']} · 임대조건 맞음 {s['rent_ok']} 틀림 {s['rent_wrong']} 못 읽음 {s['rent_missing']}")
    print(f"[LH 읽기 도구] 지금 공고 {coverage['notices']}건 중 읽은 글 pypdf {coverage['pypdf']} · pdfium {coverage['pdfium']} · pdfplumber {coverage['plumber']}")
    print(f"[LH 읽기 도구] 합친 결과 틀림 {out['merged_wrong']} · 보완 {len(merge_notes)} · 도구끼리 다름(확인 필요) {len(conflicts)}")
    return 1 if out["merged_wrong"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
