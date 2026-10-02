"""데이터 불변식 검사 (기능: qa_gate, 2026-10-02 MASTER QA 4·11·26항). 지금 공고(docs/listings.json)와 지난 공고 보관함(docs/archive/past.json)에서
'항상 성립해야 하는 규칙'을 전부 검사해 evidence/qa/invariants.json 에 남긴다. 예상된 차이(신혼희망타운은 특공 유형별 세대가 없고 합계만 옴)는 예외로 적는다.
실행: python -m tools.qa.invariants  (위반이 있으면 종료 코드 1)"""
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEEP_AFTER_WINNER_DAYS = 14   # app/sources/applyhome.py 와 같은 값 — 발표 뒤 이 날짜가 지난 공고가 목록에 남아 있으면 오래된 데이터를 조용히 보여주는 것
TYPES = {"general": {"APT", "신혼희망타운"}, "remainder": {"무순위", "불법행위 재공급"}}


def check(rows: list, today: str, live: bool) -> dict:
    bad: dict = {}
    def f(name, x, why=""):
        bad.setdefault(name, []).append(f"{x.get('id')} {why}".strip())
    for k, v in Counter(x["id"] for x in rows).items():
        if v > 1:
            f("ID 중복", {"id": k}, f"{v}번")
    for x in rows:
        cat, st = x.get("category"), x.get("supply_type") or x.get("kind")
        if cat not in TYPES:
            f("공급 구분 값", x, repr(cat))
        elif live and st not in TYPES[cat]:
            f("공급유형 ↔ 구분 상호배타", x, f"{cat} / {st}")
        if cat == "remainder" and x.get("house_dtl"):
            f("무순위인데 국민/민영 값", x, x.get("house_dtl"))
        p = x.get("price")
        lo = 0.1 if x.get("rental") else 0.3
        if p is None or not (lo <= p <= 200):
            f("금액 범위 (억)", x, repr(p))
        if not x.get("area") or x["area"] <= 0 or x["area"] > 300:
            f("전용면적", x, repr(x.get("area")))
        if (x.get("households") or 0) < 0:
            f("세대수 음수", x, repr(x.get("households")))
        su = x.get("special_units") or {}
        if su.get("total") is not None:
            parts = sum(v for k, v in su.items() if k != "total" and isinstance(v, int))
            town = "신혼희망타운" in (x.get("kind") or "") + (x.get("supply_type") or "")
            if parts != su["total"] and not (town and parts == 0):
                f("특공 유형별 합 ≠ 합계", x, f"{parts} ≠ {su['total']}")
            if any(isinstance(v, int) and v < 0 for v in su.values()):
                f("특공 세대 음수", x)
        ds = [x.get("notice"), x.get("apply"), x.get("apply_end") or x.get("apply"), x.get("winner")]
        ds = [d for d in ds if d]
        if ds != sorted(ds):
            f("날짜 순서", x, " ≤ ".join(ds))
        if not x.get("sido"):
            f("시·도 없음", x)
        if x.get("rental") and (x.get("category") != "general" or x.get("mkt_low") is not None):
            f("공공임대인데 일반분양 아님·시세 있음", x)
        if live:
            end, win = x.get("apply_end") or x.get("apply"), x.get("winner")
            keep = (date.fromisoformat(win) + timedelta(days=KEEP_AFTER_WINNER_DAYS)).isoformat() if win else end
            if keep and keep < today:
                f("보관 기간 지난 공고가 목록에 남음", x, f"발표 {win}")
    return {"rows": len(rows), "violations": {k: {"count": len(v), "examples": v[:5]} for k, v in bad.items()}}


def main() -> int:
    today = date.today().isoformat()
    L = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    L = L["listings"] if isinstance(L, dict) else L
    A = json.loads((ROOT / "docs" / "archive" / "past.json").read_text(encoding="utf-8"))["items"]
    rep = {"date": today, "live": check(L, today, True), "archive": check(A, today, False)}
    n = sum(v["count"] for s in ("live", "archive") for v in rep[s]["violations"].values())
    rep["ok"] = n == 0
    out = ROOT / "evidence" / "qa" / "invariants.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[QA 불변식] 지금 {rep['live']['rows']}주택형 · 보관 {rep['archive']['rows']}주택형 · 위반 {n}건")
    for s in ("live", "archive"):
        for k, v in rep[s]["violations"].items():
            print(f"[QA 불변식·위반] {s} {k} {v['count']}건: {', '.join(v['examples'][:3])}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
