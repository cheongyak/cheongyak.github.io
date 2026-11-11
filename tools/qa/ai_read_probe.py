"""AI 판독 정확도 시험 (기능 ai_read) — 정답 데이터가 있는 LH 임대 공고문을 AI 에게 **통째로** 읽히고(규칙이 읽은 값은 주지 않는다), 검사기를 거친 값을 정답과 견준다.

스위치를 켜기 전·지시문(PROMPT_V)이나 검사기를 바꾼 뒤에 돌린다. 실제 Claude 를 부르므로 Actions(ai-read-probe.yml, ANTHROPIC_API_KEY)에서 돈다.
칸마다: 맞음 / **틀림(검사기를 통과했는데 정답과 다름 — 0 이어야 한다)** / 검사기가 버림(맞는 값을 버림·틀린 값을 걸러냄) / AI 가 못 읽음 / 정답에 없는 값.
결과: evidence/qa/ai-read-probe.json, AI 답은 evidence/qa/ai-probe/<id>.json (같은 공고문·같은 지시문이면 다시 부르지 않는다).
실행: python -m tools.qa.ai_read_probe [공고 수=12] [--ids id,id]"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app import ai_read  # noqa: E402
from tools.qa.lh_pdf_tools import texts_of  # noqa: E402

OUT = ROOT / "evidence" / "qa" / "ai-read-probe.json"
CACHE = ROOT / "evidence" / "qa" / "ai-probe"
KEYS = [("장기종사자", "장기종사자"), ("대학생", "대학생"), ("신혼부부·한부모", "신혼|한부모"), ("청년", "청년"), ("고령자", "고령자"), ("주거급여수급자", "주거급여"), ("일반", "일반")]
FIELDS = ("homeless", "income_pct", "asset_manwon", "car_manwon")


def _key(name):
    return next((k for k, p in KEYS if re.search(p, name or "")), name)


def _norm(f, v):
    if f == "income_pct" and isinstance(v, dict):
        return {k: v.get(k) for k in ("1", "2", "3+")}
    if f == "regions" and isinstance(v, list):
        return sorted(v)
    if f == "account" and isinstance(v, dict):
        return {k: v.get(k) for k in ("months", "count", "rank2_any")}
    if f == "local" and isinstance(v, dict):
        return {k: v.get(k) for k in ("sido", "sigun")}
    return v


def answer_of(g: dict, tx: dict, key: str) -> tuple[dict | None, float, str]:
    """→ (AI 답, 이번에 쓴 추정 달러, 기록)"""
    text = next(iter(tx.values()))
    f = CACHE / f"{g['id']}.json"
    try:
        s = json.loads(f.read_text(encoding="utf-8"))
        if s.get("sha") == ai_read.sha(text) and s.get("prompt_v") == ai_read.PROMPT_V:
            return s["answer"], 0.0, "저장해 둔 답"
    except Exception:
        pass
    if not key:
        return None, 0.0, "ANTHROPIC_API_KEY 없음"
    try:
        ans, usage = ai_read.ask(text, g["type"], g.get("verified_from", ""), key)
    except Exception as e:
        return None, 0.0, f"호출 실패: {str(e)[:160].replace(key, '***')}"
    usd = ai_read.usd_of(usage)
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"id": g["id"], "sha": ai_read.sha(text), "prompt_v": ai_read.PROMPT_V, "model": ai_read.MODEL, "usage": usage, "usd": round(usd, 4), "answer": ans},
                            ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return ans, usd, f"입력 {usage.get('input_tokens')}·출력 {usage.get('output_tokens')} 토큰"


def compare(g: dict, ans: dict, tx: dict, region) -> list[dict]:
    val, dropped = ai_read.to_terms(ans, list(tx.values()), region, g["type"])
    rows = []

    def row(name, f, gold, raw, got):
        gold, raw, got = _norm(f, gold), _norm(f, raw), _norm(f, got)
        if got is not None:
            res = "맞음" if got == gold else "정답에 없는 값" if gold is None else "틀림"
        elif raw is not None:
            res = "검사기가 버림(맞는 값)" if raw == gold else "검사기가 버림(틀린 값)" if gold is not None else "검사기가 버림(정답 없음)"
        else:
            res = "AI 못 읽음" if gold is not None else None
        if res:
            rows.append({"id": g["id"], "field": name, "result": res, "gold": gold, "ai": raw, "passed": got})

    A = {_key(x.get("key")): x for x in ans.get("groups") or [] if isinstance(x, dict)}
    V = {x["key"]: x for x in val.get("groups") or []}
    for gg in g.get("groups") or []:
        k = _key(gg["name"])
        for f in FIELDS:
            row(f"{k}.{f}", f, gg.get(f), (A.get(k) or {}).get(f), (V.get(k) or {}).get(f))
    for k in set(A) - {_key(gg["name"]) for gg in g.get("groups") or []}:
        if k in V:
            rows.append({"id": g["id"], "field": f"계층 {k}", "result": "정답에 없는 계층", "gold": None, "ai": None, "passed": {f: V[k].get(f) for f in FIELDS}})
    for f in ("regions", "account"):
        if f in g or ans.get(f) is not None:
            row(f, f, g.get(f), ans.get(f), val.get(f))
    if g.get("local") or ans.get("local"):
        row("local", "local", g.get("local"), ans.get("local"), val.get("local"))
    for r in rows:
        r["dropped_why"] = next((d for d in dropped if d.startswith(r["field"] + ":")), None) if "버림" in r["result"] else None
    return rows


def sale_main(n: int) -> int:
    """분양(기능 ai_read_sale): 정답 데이터(tests/golden/notices.json)에 거주 지역 요건이 있는 공고문을 AI 에게 읽히고, 검사기를 거친 값을 정답과 견준다."""
    from collections import Counter
    from app.notice_pdf import _area
    gold = json.loads((ROOT / "tests/golden/notices.json").read_text(encoding="utf-8"))
    out_f, cache = ROOT / "evidence" / "qa" / "ai-read-probe-sale.json", ROOT / "evidence" / "qa" / "ai-probe-sale"

    def text_of(nid):
        for d in ("evidence/notices", "evidence/qa/notices"):
            f = ROOT / d / f"{nid}.txt"
            if f.exists():
                return f.read_text(encoding="utf-8", errors="replace")
        return ""

    pick = sorted((k for k, v in gold.items() if isinstance(v, dict) and isinstance((v.get("fields") or {}).get("residence"), dict) and text_of(k)), reverse=True)[:n]
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    rows, notes, usd = [], [], 0.0
    for nid in pick:
        g, text = gold[nid]["fields"], text_of(nid)
        f = cache / f"{nid}.json"
        ans = None
        try:
            sv = json.loads(f.read_text(encoding="utf-8"))
            if sv.get("prompt_v") == ai_read.SALE_PROMPT_V:
                ans = sv["answer"]
        except Exception:
            pass
        if ans is None:
            if not key:
                notes.append({"id": nid, "note": "ANTHROPIC_API_KEY 없음"})
                continue
            try:
                ans, usage = ai_read.ask(text, "분양", gold[nid].get("name", ""), key, None, ai_read.SYSTEM_SALE)
            except Exception as e:
                notes.append({"id": nid, "note": f"호출 실패: {str(e)[:160].replace(key, '***')}"})
                continue
            usd += ai_read.usd_of(usage)
            cache.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps({"id": nid, "prompt_v": ai_read.SALE_PROMPT_V, "model": ai_read.MODEL, "usage": usage, "answer": ans}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        hints, dropped = ai_read.sale_hints(ans, [text])

        def norm_res(v):
            if not isinstance(v, dict):
                return None
            a = v.get("area")
            a = _area(a) if isinstance(a, str) else a
            return {"sido": (a or {}).get("sido"), "sigungu": (a or {}).get("sigungu"), "months": v.get("months"), "since": v.get("since") if v.get("months") else None,
                    "others": sorted(v.get("others") or [])}

        for fld, gv, raw, got in (("residence", norm_res(g.get("residence")), norm_res(ans.get("residence")), norm_res((hints.get("residence") or {}).get("value"))),
                                  ("residence_duty", g.get("residence_duty"), ans.get("residence_duty_years"), (hints.get("residence_duty") or {}).get("years"))):
            if fld == "residence_duty" and "residence_duty" not in g:
                gv = None
            if got is not None:
                res = "맞음" if got == gv else "정답에 없는 값" if gv is None else "틀림"
            elif raw is not None:
                res = "검사기가 버림(맞는 값)" if raw == gv else "검사기가 버림(틀린 값)" if gv is not None else "검사기가 버림(정답 없음)"
            else:
                res = "AI 못 읽음" if gv is not None else None
            if res:
                rows.append({"id": nid, "field": fld, "result": res, "gold": gv, "ai": raw, "passed": got,
                             "dropped_why": next((d for d in dropped if d.startswith(fld + ":")), None) if "버림" in res else None})
    c = Counter(r["result"] for r in rows)
    res = {"at": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "model": ai_read.MODEL, "prompt_v": ai_read.SALE_PROMPT_V, "notices": len(pick),
           "usd": round(usd, 3), "summary": dict(c), "wrong": [r for r in rows if r["result"] in ("틀림", "정답에 없는 값")], "notes": notes, "rows": rows}
    out_f.parent.mkdir(parents=True, exist_ok=True)
    out_f.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[AI 판독 시험·분양] 공고 {len(pick)}건 · " + " · ".join(f"{k} {v}" for k, v in c.most_common()) + f" · 이번 추정 비용 ${usd:.2f}")
    for r in res["wrong"]:
        print(f"  [{r['result']}] {r['id']} {r['field']}: 정답 {r['gold']!r} ↔ AI {r['passed']!r}")
    for x in notes:
        print(f"  [답 없음] {x['id']} {x['note']}")
    return 0


def main() -> int:
    if "--sale" in sys.argv:
        a = [x for x in sys.argv[1:] if not x.startswith("--")]
        return sale_main(int(a[0]) if a else 15)
    gold = json.loads((ROOT / "tests/golden/lh_rental.json").read_text(encoding="utf-8"))["notices"]
    units = {n["id"]: n for n in json.loads((ROOT / "tests/qa/lh/rental_units.json").read_text(encoding="utf-8"))}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 12
    ids = sys.argv[sys.argv.index("--ids") + 1].split(",") if "--ids" in sys.argv else None
    pick = [g for g in gold if texts_of(g["id"])]
    pick = [g for g in pick if g["id"] in ids] if ids else sorted(pick, key=lambda g: g.get("posted") or "", reverse=True)[:n]
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    rows, notes, usd = [], [], 0.0
    for g in pick:
        tx = texts_of(g["id"])
        ans, cost, note = answer_of(g, tx, key)
        usd += cost
        notes.append({"id": g["id"], "type": g["type"], "note": note})
        if ans is None:
            continue
        rows += compare(g, ans, tx, (units.get(g["id"]) or {}).get("region"))
    from collections import Counter
    c = Counter(r["result"] for r in rows)
    res = {"at": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "model": ai_read.MODEL, "prompt_v": ai_read.PROMPT_V,
           "notices": len(pick), "answered": sum(1 for x in notes if "실패" not in x["note"] and "없음" not in x["note"]), "usd": round(usd, 3),
           "summary": dict(c), "wrong": [r for r in rows if r["result"] in ("틀림", "정답에 없는 값", "정답에 없는 계층")], "notes": notes, "rows": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[AI 판독 시험] 공고 {res['notices']}건(답 받음 {res['answered']}) · " + " · ".join(f"{k} {v}" for k, v in c.most_common()) + f" · 이번 추정 비용 ${usd:.2f}")
    for r in res["wrong"]:
        print(f"  [{r['result']}] {r['id']} {r['field']}: 정답 {r['gold']!r} ↔ AI {r['passed']!r}")
    for x in notes:
        if "실패" in x["note"] or "없음" in x["note"]:
            print(f"  [답 없음] {x['id']} {x['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
