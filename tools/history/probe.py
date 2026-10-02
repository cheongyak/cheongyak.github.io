"""2026 과거 공고 실험 (기능: historical, 2026-10-02 사용자 요청 '현재꺼 백업하고 과거 데이터까지 넣어 보고, 활용도 없거나 느리면 폐기').
1단계 측정만: 청약홈 API 에서 2026-01-01 이후 공고 개요를 받아 건수·월별·유형별·필드·예상 호출 수를 evidence/history/probe.json 에 남긴다.
서비스 데이터(docs/)는 건드리지 않는다. 실행: python -m tools.history.probe  (DATA_GO_KR_KEY 필요, Actions history.yml)"""
import collections
import json
import time
from pathlib import Path

from app.sources.applyhome import ApplyhomeClient, pick, to_date

OUT = Path(__file__).resolve().parents[2] / "evidence" / "history" / "probe.json"
SINCE = "2026-01-01"


def main() -> None:
    ah = ApplyhomeClient()
    t0 = time.monotonic()
    rep = {"since": SINCE, "at": time.strftime("%Y-%m-%d %H:%M"), "categories": {}}
    calls = 0
    for cat in ("general", "remainder"):
        rows = ah.notices(cat, since=SINCE, max_pages=80)
        calls += max(1, (len(rows) + 99) // 100)
        by_month = collections.Counter((to_date(pick(d, "notice")) or "")[:7] for d in rows)
        names = [str(pick(d, "name") or "") for d in rows]
        keys = sorted({k for d in rows[:200] for k in d.keys()})
        marks = {w: sum(1 for n in names if w in n) for w in ("정정", "취소", "재공고", "추가", "잔여", "재공급")}
        kinds = collections.Counter(str(pick(d, "kind") or "") for d in rows)
        ids = [str(pick(d, "notice_no") or "") for d in rows]
        rep["categories"][cat] = {"notices": len(rows), "unique_ids": len(set(ids)), "by_month": dict(sorted(by_month.items())),
                                  "kinds": dict(kinds.most_common(12)), "name_marks": marks, "fields": keys,
                                  "oldest": min((to_date(pick(d, "notice")) or "9" for d in rows), default=None)}
    # 주택형 조회 비용 표본: 20건만 실제로 불러 평균 주택형 수를 잰다
    sample = []
    for cat in ("general", "remainder"):
        rows = ah.notices(cat, since=SINCE, max_pages=1)[:10]
        for d in rows:
            no = str(pick(d, "notice_no") or "")
            if no:
                sample.append(len(ah.models(cat, no)))
                calls += 1
    total = sum(c["notices"] for c in rep["categories"].values())
    rep["models_per_notice_avg"] = round(sum(sample) / len(sample), 1) if sample else None
    rep["estimate"] = {"notices_2026": total, "model_calls_needed": total, "types_estimated": round(total * (rep["models_per_notice_avg"] or 0))}
    rep["calls_this_run"] = calls
    rep["seconds"] = round(time.monotonic() - t0, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "categories"}, ensure_ascii=False))
    for cat, c in rep["categories"].items():
        print(cat, c["notices"], c["by_month"], c["name_marks"])


if __name__ == "__main__":
    main()
