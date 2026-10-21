"""수집 멈춤 감시 — 데이터 파일의 '마지막 갱신' 이 너무 오래되면 경고 (2026-10-22 LH 임대 수집이 10-20 낮 뒤로 이틀 멈춘 일).

그때 수집 자체는 매일 돌았지만 '저장' 단계가 실패해 결과가 올라가지 않았다. 실행 목록의 실패는 메일이 잘 안 보이고,
아침 공고 수집(collect)·검증 요약은 LH 파일 시각을 보지 않아 이틀 동안 아무도 몰랐다.

보는 것 (마지막 갱신 시각, 한국 시각 'YYYY-MM-DD HH:MM'):
 - 분양      docs/updated.txt                 (청약 공고 수집, 매일 05:30)
 - LH 임대   docs/lh-rental.json  updated     (LH 임대 수집, 매일 06:40 — 공고가 그대로여도 매번 시각을 새로 씀)
 - SH 임대   docs/sh-rental.json  updated     (SH 임대 수집, 매일 06:50)
 - GH 임대·공공지원 민간임대는 화면 스위치(gh_rental·pvt_rental)가 켜졌을 때만
기준: 26시간 (매일 한 번 도는 수집 + 예약 지연 여유). 넘으면 [경고·수집 멈춤] 줄 → 실행 기록(run-log)·수집 알림 이슈·verify-status warnings.
결과: evidence/qa/freshness.json. 실행: python -m tools.qa.freshness [--hours 26]
판정 검증 성공 여부(ok)는 바꾸지 않는다 — 데이터가 틀린 게 아니라 오래된 것이라 '경고'로만 알린다."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "freshness.json"
KST = timezone(timedelta(hours=9))
LIMIT_HOURS = 26

# (이름, 파일, 시각 읽는 법, 이 원천을 보는 화면 스위치 — None 이면 늘 봄)
SOURCES = [
    ("분양", "docs/updated.txt", "text", None),
    ("LH 임대", "docs/lh-rental.json", "json", "lh_rental"),
    ("SH 임대", "docs/sh-rental.json", "json", "sh_rental"),
    ("GH 임대", "docs/gh-rental.json", "json", "gh_rental"),
    ("공공지원 민간임대", "docs/pvt-rental.json", "json", "pvt_rental"),
]


def _features(root: Path) -> dict:
    try:
        return json.loads((root / "docs" / "config.json").read_text(encoding="utf-8")).get("features", {}) or {}
    except Exception:
        return {}


def _parse(s) -> datetime | None:
    try:
        return datetime.strptime(str(s).strip()[:16], "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except Exception:
        return None


def read_updated(root: Path, path: str, how: str) -> str | None:
    p = root / path
    if not p.exists():
        return None
    try:
        if how == "text":
            return p.read_text(encoding="utf-8").strip() or None
        return json.loads(p.read_text(encoding="utf-8")).get("updated")
    except Exception:
        return None


def check(root: Path = ROOT, now: datetime | None = None, limit: float = LIMIT_HOURS) -> dict:
    now = now or datetime.now(KST)
    feats = _features(root)
    items = []
    for name, path, how, switch in SOURCES:
        if switch is not None and feats.get(switch, True) is False:
            continue   # 화면에 안 쓰는 원천은 멈춰도 사용자에게 영향이 없다
        raw = read_updated(root, path, how)
        at = _parse(raw)
        hours = round((now - at).total_seconds() / 3600, 1) if at else None
        items.append({"name": name, "file": path, "updated": raw, "hours": hours,
                      "stale": hours is None or hours > limit})
    stale = [i for i in items if i["stale"]]
    return {"checked": now.strftime("%Y-%m-%d %H:%M"), "limit_hours": limit, "items": items, "stale": len(stale),
            "warnings": [f"{i['name']} 데이터가 {i['hours']:.0f}시간째 갱신되지 않음 (마지막 {i['updated']})" if i["hours"] is not None
                         else f"{i['name']} 데이터의 갱신 시각을 읽지 못함 ({i['file']})" for i in stale]}


def lines(r: dict) -> list[str]:
    out = [f"[경고·수집 멈춤] {w} — 기준 {r['limit_hours']:.0f}시간. 그 수집 Actions 실행 결과(저장 단계)를 확인" for w in r["warnings"]]
    out.append("[수집 신선도] " + " · ".join(f"{i['name']} {i['updated'] or '?'}" + (f"({i['hours']:.0f}시간 전)" if i["hours"] is not None else "")
                                         for i in r["items"]) + (f" — 멈춤 {r['stale']}" if r["stale"] else " — 정상"))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=LIMIT_HOURS)
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    r = check(limit=a.hours)
    if not a.no_save:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n".join(lines(r)))
    return 0   # 경고만 — 실패로 끝내지 않는다 (수집·검증 흐름을 막지 않게)


if __name__ == "__main__":
    sys.exit(main())
