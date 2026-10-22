"""'베타 참고용' 경고 이력 (2026-10-22 사용자 지시문 '반복 오류를 찾는 기능').

화면 경고는 docs/verify-status.json 을 읽으므로, 저장소에 남은 그 파일의 모든 판(git 이력)을 시간순으로 다시 읽어
경고가 켜진 구간(ok=false 가 이어진 동안)을 모으고, 구간마다 어떤 검사가 걸렸는지·얼마나 켜져 있었는지·지금 규칙(기능 verify_scope)이면
사이트 전체 경고였을지 공고별 표시였을지를 남긴다. 원인 분류는 사람이 원문·커밋으로 확인한 값만 evidence/qa/warn-causes.json 에 적는다(추측 금지).
결과: evidence/qa/warn-history.json · 실행: python -m tools.qa.warn_history  (얕은 clone 이면 `git fetch --unshallow` 먼저)
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "warn-history.json"
CAUSES = ROOT / "evidence" / "qa" / "warn-causes.json"
KST = timezone(timedelta(hours=9))
# verify-status.json qa 칸 → 지금 규칙의 범위 (tools/verify_status.scope 와 같은 나눔)
LISTING = {"invariant_violations", "lh_invariant_violations", "lh_unread", "market_fails", "pay_audit_bad", "parse_moved_changes"}
NOTICE = {"crosscheck", "golden", "lh_pdf_merged_wrong"}
UNVERIFIED = {"crosscheck_none", "judge_none"}


def reasons(d: dict) -> list[str]:
    r = []
    j = d.get("judge")
    if not j:
        r.append("judge_none")
    elif j.get("failed"):
        r.append(f"judge:{len(j['failed'])}")
    cc = d.get("crosscheck") or {}
    if cc.get("mismatches"):
        r.append(f"crosscheck:{len(cc['mismatches'])}")
    if cc.get("summary") is None:
        r.append("crosscheck_none")
    if (d.get("golden") or {}).get("mismatches"):
        r.append(f"golden:{len(d['golden']['mismatches'])}")
    for k, v in (d.get("qa") or {}).items():
        if isinstance(v, int) and not isinstance(v, bool) and v and k not in ("cross_rule_checks",):
            r.append(f"{k}:{v}")
    return r


def scope_of(rs: list[str]) -> str:
    keys = {x.split(":")[0] for x in rs}
    if keys & UNVERIFIED:
        return "전체·검증 미완료"
    if keys & NOTICE:
        return "전체·공고문 불일치"
    if keys - LISTING:
        return "전체·판정 계산"
    return "공고별 표시"


def snapshots() -> list[tuple]:
    lines = subprocess.run(["git", "log", "--format=%H %cI", "--", "docs/verify-status.json"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    out = []
    for line in lines:
        if not line.strip():
            continue
        h, t = line.split()
        try:
            d = json.loads(subprocess.run(["git", "show", f"{h}:docs/verify-status.json"], cwd=ROOT, capture_output=True, text=True).stdout)
        except Exception:
            continue
        out.append((datetime.fromisoformat(t).astimezone(KST), h, d))
    return sorted(out, key=lambda x: x[0])


def episodes(snaps: list[tuple]) -> list[dict]:
    eps, cur = [], None
    for t, h, d in snaps:
        if d.get("ok") is False:
            if cur is None:
                cur = {"start": t, "start_commit": h[:8], "reasons": []}
            cur["reasons"] += [x for x in reasons(d) if x not in cur["reasons"]]
        elif cur:
            cur["end"], cur["end_commit"] = t, h[:8]
            eps.append(cur)
            cur = None
    if cur:
        cur["end"], cur["end_commit"] = None, None
        eps.append(cur)
    return eps


def main() -> int:
    snaps = snapshots()
    causes = json.loads(CAUSES.read_text(encoding="utf-8")) if CAUSES.exists() else {}
    eps = episodes(snaps)
    rows = []
    for e in eps:
        hours = round((e["end"] - e["start"]).total_seconds() / 3600, 1) if e["end"] else None
        c = causes.get(e["start_commit"]) or {}
        rows.append({"start": e["start"].strftime("%Y-%m-%d %H:%M"), "end": e["end"] and e["end"].strftime("%Y-%m-%d %H:%M"), "hours": hours,
                     "start_commit": e["start_commit"], "end_commit": e["end_commit"], "checks": e["reasons"], "now_shown_as": scope_of(e["reasons"]),
                     "cause": c.get("cause"), "kind": c.get("kind"), "true_error": c.get("true_error"), "fix": c.get("fix")})
    by_kind = Counter(r["kind"] or "원인 미기록" for r in rows)
    hours_kind = Counter()
    for r in rows:
        hours_kind[r["kind"] or "원인 미기록"] += r["hours"] or 0
    res = {"generated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "snapshots": len(snaps), "episodes": len(rows),
           "hours": round(sum(r["hours"] or 0 for r in rows), 1), "by_kind": dict(by_kind.most_common()),
           "hours_by_kind": {k: round(v, 1) for k, v in hours_kind.most_common()},
           "now_shown_as": dict(Counter(r["now_shown_as"] for r in rows).most_common()),
           "true_errors": sum(1 for r in rows if r["true_error"] is True), "false_alarms": sum(1 for r in rows if r["true_error"] is False),
           "uncaused": [r["start_commit"] for r in rows if not r["kind"]], "rows": rows}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    scr = sum(1 for r in rows if r["true_error"] is True and r["kind"] == "화면 코드 회귀")
    print(f"[경고 이력] verify-status 판 {res['snapshots']}개 · 경고 구간 {res['episodes']}번 · 합계 {res['hours']}시간 · 실제 오류 {res['true_errors']}(데이터 {res['true_errors'] - scr}·화면 코드 {scr}) · 거짓 경보 {res['false_alarms']}")
    for k, n in res["by_kind"].items():
        print(f"[경고 이력·원인] {k}: {n}번 · {res['hours_by_kind'][k]}시간")
    for k, n in res["now_shown_as"].items():
        print(f"[경고 이력·지금 규칙] {k}: {n}번")
    if res["uncaused"]:
        print(f"[경고 이력·원인 미기록] {' '.join(res['uncaused'])} — 원문·커밋으로 원인을 확인해 {CAUSES.relative_to(ROOT)} 에 적을 것")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
