"""오늘 고칠 '공고문 못 읽음' 목록 (2026-10-22 사용자 '처음 보는 공고 형태가 나오면 자체적으로 새 읽는 방식을 추가해서 읽던지').

매일 아침 자동 고치기 세션(.claude/skills/cheongyakpass-ops/AUTOFIX.md)이 이 목록부터 본다. 모으는 것:
  - 분양: docs/listings.json 각 주택형 checks 중 app.check_audit 분류가 '공고문 못 읽음'(unread)·'공고문 대조'(notice)·'분류 안 된 새 문구'(other)
  - 임대: evidence/qa/lh-unread.json 허용 목록 밖 줄, evidence/qa/lh-invariants.json terms_unread
  - 검증: docs/verify-status.json banner·flagged (경고·공고별 표시)
  - 실행 기록: docs/run-log.txt [공고문·정정]·[공고문·법령 불일치]·[공고문·불일치]
공고마다 원문이 저장소에 있는지(evidence/notices·evidence/qa/notices·docs/chat-notice) 함께 적는다 — 없으면 '근거 자료 모으기'(probe.yml)를 돌려 받는다.
결과: evidence/qa/unread-queue.json · 실행: python -m tools.qa.unread_queue (항목이 없으면 '할 일 없음')
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "evidence" / "qa" / "unread-queue.json"


def original(nid: str) -> str | None:
    for p in (ROOT / "evidence" / "notices" / f"{nid}.txt", ROOT / "evidence" / "qa" / "notices" / f"{nid}.txt", ROOT / "docs" / "chat-notice" / f"{nid}.json"):
        if p.exists():
            return str(p.relative_to(ROOT))
    return None


def load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def build() -> dict:
    from app.check_audit import NAME, category
    items: dict[str, dict] = {}

    def add(nid, name, src, kind, msg, field=None):
        it = items.setdefault(nid, {"nid": nid, "name": name, "original": original(nid), "problems": []})
        p = {"src": src, "kind": kind, "msg": msg}
        if field:
            p["field"] = field
        if p not in it["problems"]:
            it["problems"].append(p)

    rows = load(ROOT / "docs" / "listings.json", [])
    rows = rows["listings"] if isinstance(rows, dict) else rows
    for r in rows:
        nid = r["id"].split("-")[0]
        for c in r.get("checks") or []:
            k = category(c)
            if k in ("unread", "notice", "other"):
                add(nid, r.get("name"), "분양", NAME[k], c, r["id"].split("-", 1)[1].strip())
        for c in r.get("notice_conflicts") or []:
            add(nid, r.get("name"), "분양", "공고문 대조", c, r["id"].split("-", 1)[1].strip())
    lhu = load(ROOT / "evidence" / "qa" / "lh-unread.json", {})
    for r in lhu.get("rows") or []:
        if not r.get("allowed"):
            add(r["id"], r.get("name"), "임대", "공고문 못 읽음", f"{r.get('group')} {r.get('text')}")
    lhi = load(ROOT / "evidence" / "qa" / "lh-invariants.json", {})
    for k, v in (lhi.get("violations") or {}).items():
        for e in v.get("examples") or []:
            add(e.split(" ")[0], None, "임대", "임대 불변식", f"{k}: {e}")
    vs = load(ROOT / "docs" / "verify-status.json", {})
    for i, rs in (vs.get("flagged") or {}).items():
        for r in rs:
            add(i.split("-")[0], None, "검증", "공고별 표시", r)
    log = (ROOT / "docs" / "run-log.txt").read_text(encoding="utf-8").splitlines() if (ROOT / "docs" / "run-log.txt").exists() else []
    names = {r.get("name"): r["id"].split("-")[0] for r in rows}
    for line in log:
        m = re.match(r"\[(공고문·정정|공고문·법령 불일치|공고문·불일치)\] ([^:]+?)(?: \S+)?: (.*)", line)
        if m:
            nid = names.get(m.group(2).strip()) or next((v for k, v in names.items() if k and m.group(2).startswith(k)), None)
            if nid:
                add(nid, m.group(2).strip(), "실행 기록", m.group(1), m.group(3))
    kst = timezone(timedelta(hours=9))
    out = {"generated": datetime.now(kst).strftime("%Y-%m-%d %H:%M"), "verify_ok": vs.get("ok"), "banner": vs.get("banner"),
           "count": len(items), "missing_original": sorted(k for k, v in items.items() if not v["original"]),
           "items": sorted(items.values(), key=lambda x: x["nid"])}
    return out


def main() -> int:
    q = build()
    OUT.write_text(json.dumps(q, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if not q["count"] and not q["banner"]:
        print(f"[못 읽음 목록] 할 일 없음 (검증 ok={q['verify_ok']})")
        return 0
    print(f"[못 읽음 목록] 공고 {q['count']}건 · 원문 없음 {len(q['missing_original'])}건 · 전체 경고 {q['banner'] and q['banner']['kind']}")
    for it in q["items"]:
        print(f"  {it['nid']} {it['name'] or ''} (원문 {it['original'] or '없음'})")
        for p in it["problems"][:6]:
            print(f"    - [{p['src']}·{p['kind']}] {p.get('field') or ''} {p['msg'][:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
