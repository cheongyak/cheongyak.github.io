"""푸시 알림 (ntfy).

웹 앱의 "알림 받기" 버튼은 ntfy 주제(topic) 구독 페이지로 연결된다. 구독자는 ntfy 앱이나 브라우저로 알림을 받는다.
매일 수집이 끝나면 여기서 보낸다:
  1. 새로 올라온 로또·고려 공고 (지난 실행의 docs/listings.json 과 비교)
  2. 로또·고려 공고의 접수 전날 알림
설정은 docs/config.json.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import httpx

from .engine import grade
from .models import Listing

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "docs" / "config.json"
PREVIOUS = ROOT / "docs" / "listings.json"


def load_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_previous_ids() -> Optional[set[str]]:
    """지난 실행 결과의 공고 id. 파일이 없으면 None (첫 실행이라 '새 공고' 알림을 보내지 않는다)."""
    try:
        return {x["id"] for x in json.loads(PREVIOUS.read_text(encoding="utf-8"))}
    except Exception:
        return None


def _by_notice(listings: list[Listing]) -> dict[str, list[Listing]]:
    groups: dict[str, list[Listing]] = {}
    for L in listings:
        groups.setdefault(L.id.split("-")[0], []).append(L)
    return groups


def _line(Ls: list[Listing]) -> str:
    best = max(Ls, key=lambda L: grade(L)["lo"] or -99)
    g = grade(best)
    units = ", ".join(sorted({L.unit for L in Ls}))
    return (f"[{g['name']}] {best.name} ({best.sigungu or best.region}) {units} · 마진 {g['lo']:+.1f}~{g['hi']:+.1f}억"
            f" · 접수 {best.apply or '미정'}")


def build_messages(listings: list[Listing], previous_ids: Optional[set[str]], today: date, cfg: dict) -> list[dict]:
    want = set(cfg.get("notify_grades", ["lotto", "consider"]))
    good = [L for L in listings if grade(L)["grade"] in want]
    msgs: list[dict] = []

    if previous_ids is not None:
        new = [L for L in good if L.id not in previous_ids]
        if new:
            groups = _by_notice(new)
            has_lotto = any(grade(L)["grade"] == "lotto" for L in new)
            msgs.append({
                "title": f"{'로또' if has_lotto else '고려할 만한'} 청약 {len(groups)}건이 새로 올라왔어요",
                "body": "\n".join(_line(Ls) for Ls in groups.values()),
                "priority": "high" if has_lotto else "default",
                "tags": "house",
            })

    soon = (today + timedelta(days=int(cfg.get("remind_days_before", 1)))).isoformat()
    due = [L for L in good if L.apply == soon]
    if due:
        groups = _by_notice(due)
        msgs.append({
            "title": f"내일 접수: {', '.join(Ls[0].name for Ls in groups.values())}",
            "body": "\n".join(_line(Ls) for Ls in groups.values()) + "\n자격과 자금 계획을 앱에서 확인하세요.",
            "priority": "high",
            "tags": "alarm_clock",
        })
    return msgs


def send(msgs: list[dict], cfg: dict, client: Optional[httpx.Client] = None) -> list[str]:
    topic, server = cfg.get("ntfy_topic"), cfg.get("ntfy_server", "https://ntfy.sh")
    if not topic or not msgs:
        return []
    http = client or httpx.Client(timeout=15)
    log = []
    for m in msgs:
        payload = {"topic": topic, "title": m["title"], "message": m["body"], "tags": [m["tags"]],
                   "priority": {"high": 4, "default": 3}.get(m["priority"], 3)}
        if cfg.get("site_url"):
            payload["click"] = cfg["site_url"]
        try:
            r = http.post(server, json=payload)
            log.append(f"알림 전송 {r.status_code}: {m['title']}")
        except Exception as e:
            log.append(f"알림 실패: {m['title']} ({e})")
    return log
