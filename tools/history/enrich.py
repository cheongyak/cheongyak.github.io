"""지난 공고 '그때 넣었다면' 판정용 데이터 (기능: historical_judge, 2026-10-02 사용자 요청).
주택공급규칙 개정 시행일(2026-06-15) 이후 공고 중 마감된 것만, 매일 수집과 같은 코드(build_listing·apply_notice)로 공고 조건을 만들어
docs/archive/2026-judge.json 에 쓴다. 그 전 공고는 지금 판정 엔진(개정 후 규칙)으로 판정하면 틀릴 수 있어 넣지 않는다.
- 시세·경쟁률·위치는 붙이지 않는다(그때 값이 없음). 청약봇 공고문 조각(docs/chat-notice)도 쓰지 않는다.
- 공고문 읽은 값은 docs/archive/2026-notice-cache.json 에 보관해 다음 실행에서 다시 받지 않는다(주간 실행마다 남은 것을 이어 읽음).
실행: python -m tools.history.enrich"""
import json
import time
from datetime import date
from pathlib import Path

from app import pipeline as PL
from app.sources.applyhome import ApplyhomeClient, normalize, pick, to_date

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "archive" / "2026-judge.json"
CACHE = ROOT / "docs" / "archive" / "2026-notice-cache.json"
RULE_FROM = "2026-06-15"      # 주택공급에 관한 규칙 개정 시행일 — 이 날부터의 공고만 지금 엔진으로 판정
DROP = ("mkt_low", "mkt_base", "mkt_note", "mkt_basis", "mkt_count", "mkt_direct_excluded", "mkt_comps", "jeonse", "jeonse_note",
        "jeonse_comps", "competition", "area_comps", "sp_competition", "area_sp", "nearby", "geo", "checks", "sample")


def main() -> None:
    today = date.today().isoformat()
    orig = PL.feature_on
    PL.feature_on = lambda n: False if n in ("chatbot_notice",) else orig(n)   # 청약봇 조각 파일은 건드리지 않는다
    live = set()
    try:
        rows = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
        live = {x["id"].split("-")[0] for x in (rows["listings"] if isinstance(rows, dict) else rows)}
    except Exception:
        pass
    ah = ApplyhomeClient()
    t0, out, log, skipped_live = time.monotonic(), [], [], 0
    for cat in ("general", "remainder"):
        for d in ah.notices(cat, since=RULE_FROM, max_pages=40):
            no = str(pick(d, "notice_no") or "")
            end = to_date(pick(d, "apply_end")) or to_date(pick(d, "apply"))
            if not no or not end or end >= today:
                continue                      # 아직 마감 전은 매일 수집이 다룬다
            if no in live:
                skipped_live += 1
                continue
            nday = date.fromisoformat(to_date(pick(d, "notice")) or today)
            for m in ah.models(cat, no):
                L = PL.build_listing(normalize(d, m, cat), None, nday, {})
                if L:
                    out.append(L)
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    PL.NOTICE_BUDGET_SEC = 1500   # 매일 수집은 300초로 끊지만(그래서 첫 실행에서 154건 중 29건만 읽힘, 2026-10-02) 여기는 한 번에 끝까지 읽는다 — 보관 기록이 있어 다음엔 새 공고만
    PL.apply_notice(out, log, cache=cache)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    read = {k for k, v in cache.items() if v.get("found")}
    items = []
    for L in out:
        x = {k: v for k, v in L.model_dump().items() if k not in DROP}
        x["notice_read"] = L.id.split("-")[0] in read
        items.append(x)
    nos = {x["id"].split("-")[0] for x in items}
    meta = {"v": 1, "rule_from": RULE_FROM, "built": today, "notices": len(nos), "types": len(items),
            "notice_read": len(nos & read), "skipped_live": skipped_live, "seconds": round(time.monotonic() - t0, 1)}
    OUT.write_text(json.dumps({"meta": meta, "items": items}, ensure_ascii=False, separators=(",", ":"), default=str) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False), "bytes", OUT.stat().st_size)
    for l in log:
        if l.startswith("[시간]") or l.startswith("[경고]"):
            print(l)
    (ROOT / "evidence" / "history" / "enrich.json").write_text(json.dumps({**meta, "bytes": OUT.stat().st_size}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
