"""지난 공고 보관함 만들기 (기능: historical_search). 서비스 수집(app/pipeline)과 따로 돈다.
- 청약홈 API 에서 최근 1년 공고(일반분양·무순위, 2026-01-01 이후) 개요 + 주택형을 받아 docs/archive/past.json 에 주택형 단위로 쓴다.
- 마감된 지 1년(window.KEEP_DAYS)이 지난 공고는 지운다(1년치만 운영, 2026-10-02 사용자).
- 보관만 한다(append-only): 이미 있는 마감 주택형은 다시 받지 않고 덮어쓰지 않는다(locked_at). 아직 마감 전인 것만 갱신한다.
- 시세·공고문·경쟁률은 아직 넣지 않는다(1차는 청약홈 값만, 출처 = 청약홈). 실행: python -m tools.history.build"""
import json
import time
from datetime import date
from pathlib import Path

from app import region as RG
from app.sources.applyhome import ApplyhomeClient, normalize, pick
from tools.history import window as W

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "archive" / "past.json"
KEEP = ("notice_no", "name", "address", "kind", "category", "unit", "area", "price", "households", "special_units",
        "total_households", "notice", "apply", "apply_end", "winner", "url", "house_dtl")


def status_of(r: dict, today: str) -> str:
    end = r.get("apply_end") or r.get("apply")
    if r.get("apply") and r["apply"] > today:
        return "예정"
    return "마감" if end and end < today else "접수 중"


def main() -> None:
    today = date.today().isoformat()
    old = {}
    if OUT.exists():
        old = {x["id"]: x for x in json.loads(OUT.read_text(encoding="utf-8")).get("items", [])}
    before = len(old)
    old = {k: v for k, v in old.items() if W.in_window(v, today)}      # 마감 1년 지난 공고 지우기
    pruned = before - len(old)
    since = W.fetch_since(today)
    ah = ApplyhomeClient()
    t0, calls, skipped, added, updated = time.monotonic(), 0, 0, 0, 0
    items = dict(old)
    for cat in ("general", "remainder"):
        ds = ah.notices(cat, since=since, max_pages=80)
        calls += max(1, (len(ds) + 99) // 100)
        for d in ds:
            no = str(pick(d, "notice_no") or "")
            if not no:
                continue
            if any(k.startswith(no + "-") and v.get("locked_at") for k, v in old.items()):
                skipped += 1          # 마감 확정된 공고는 다시 받지 않는다
                continue
            ms = ah.models(cat, no)
            calls += 1
            for m in ms:
                r = normalize(d, m, cat)
                rid = f"{no}-{r.get('house_ty') or r['unit']}"
                rec = {k: r.get(k) for k in KEEP}
                if not W.in_window(rec, today):
                    continue
                rec.update(id=rid, sido=RG.sido_of(r["address"] or "") or r.get("area_code_nm"), district=RG.sigungu_any(RG.main_address(r["address"] or "")),
                           status=status_of(r, today), source="청약홈 분양정보 API", seen=old.get(rid, {}).get("seen") or today, updated=today)
                if rec["status"] == "마감":
                    rec["locked_at"] = today
                updated += rid in old
                added += rid not in old
                items[rid] = rec
    rows = sorted(items.values(), key=lambda x: (x.get("notice") or "", x["id"]), reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    meta = {"v": 2, "since": since, "cutoff": W.cutoff(today), "keep_days": W.KEEP_DAYS, "pruned": pruned, "built": today, "count": len(rows), "notices": len({x["notice_no"] for x in rows}),
            "calls": calls, "seconds": round(time.monotonic() - t0, 1), "skipped_locked": skipped, "added": added, "updated": updated}
    OUT.write_text(json.dumps({"meta": meta, "items": rows}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False), "bytes", OUT.stat().st_size)
    rep = ROOT / "evidence" / "history" / "build.json"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps({**meta, "bytes": OUT.stat().st_size}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
