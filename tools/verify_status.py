"""검증 결과 모으기 (기능: verify_status) → docs/verify-status.json

수집 실행 기록(docs/run-log.txt)의 공고문 대조·정답 데이터 결과와 판정 검증 사례 결과(docs/judge-status.json)를 한 파일로 모은다.
화면(이용 안내·베타 상자)이 이 파일로 마지막 검증 결과를 보여주고, 하나라도 다르면 종료 코드 1 → Actions 가 실패로 표시되고 이슈 알림.
실행: python -m tools.verify_status
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def build() -> dict:
    log = (DOCS / "run-log.txt").read_text(encoding="utf-8").splitlines() if (DOCS / "run-log.txt").exists() else []
    judge = json.loads((DOCS / "judge-status.json").read_text(encoding="utf-8")) if (DOCS / "judge-status.json").exists() else None
    cc_sum = next((l for l in log if l.startswith("[검증·공고문] ")), None)
    cc_bad = [l for l in log if l.startswith("[검증·공고문 불일치]")]
    gold_bad = [l for l in log if l.startswith("[검증·정답 불일치]")]
    run_at = next((l.split("실행: ")[1] for l in log if l.startswith("실행: ")), None)
    try:
        cc_on = json.loads((DOCS / "config.json").read_text(encoding="utf-8")).get("features", {}).get("notice_crosscheck", True)
    except Exception:
        cc_on = True
    ok = bool(judge) and not judge["failed"] and not judge.get("pageErrors") and not cc_bad and not gold_bad and (cc_sum is not None or not cc_on)
    kst = timezone(timedelta(hours=9))
    return {"at": datetime.now(kst).strftime("%Y-%m-%d %H:%M"), "ok": ok, "collect_run": run_at,
            "judge": {"total": judge["total"], "passed": judge["passed"], "failed": [f["id"] for f in judge["failed"]]} if judge else None,
            "crosscheck": {"summary": cc_sum, "mismatches": cc_bad[:30]}, "golden": {"mismatches": gold_bad[:30]}}


if __name__ == "__main__":
    s = build()
    (DOCS / "verify-status.json").write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[검증 요약] {'통과' if s['ok'] else '문제 있음'} · 판정 사례 {s['judge'] and s['judge']['passed']}/{s['judge'] and s['judge']['total']} · {s['crosscheck']['summary']} · 정답 불일치 {len(s['golden']['mismatches'])}건")
    sys.exit(0 if s["ok"] else 1)
