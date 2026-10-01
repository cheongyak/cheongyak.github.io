"""웹 푸시 알림 보내기 (기능: web_push).

매일 수집이 끝나면 알림 서버(push/worker.js, Cloudflare Workers)에 '이벤트'를 보낸다.
서버가 구독자마다 고른 지역·종류에 맞는 이벤트만 골라 한 통으로 묶어 보낸다.

이벤트
  new   : 지난 실행 뒤 새로 올라온 공고 (접수가 끝나지 않은 것)
  start : 내일 접수 시작 (특별공급이 있으면 특별공급 시작일, 없으면 접수 시작일)
  end   : 내일 접수 마감
공고(주택관리번호) 하나에 이벤트 하나. 주택형은 한 줄에 묶는다.

인터뷰 입력값은 알림 서버로 보내지 않으므로 '내 자격'으로 고르지 않는다. 공고의 지역(시·도)과 등급만 쓴다.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Optional

import httpx

from .engine import grade
from .models import Listing

MAX_NEW = 30          # 새 공고가 이보다 많으면 비교 기준(지난 결과)이 비정상이라 보고 보내지 않는다
MAX_CALLS = 2000      # 발송 이어 받기 상한 (구독 BATCH 10 × 2000 = 2만 명)


def _groups(listings: list[Listing]) -> dict[str, list[Listing]]:
    g: dict[str, list[Listing]] = {}
    for L in listings:
        g.setdefault(L.id.split("-")[0], []).append(L)
    return g


def _first_day(L: Listing) -> Optional[str]:
    return L.special_apply or L.apply


def _md(d: Optional[str]) -> str:
    return f"{int(d[5:7])}/{int(d[8:10])}" if d and len(d) >= 10 else "미정"


def _line(Ls: list[Listing], want: set[str]) -> tuple[str, bool]:
    best = max(Ls, key=lambda L: grade(L)["lo"] if grade(L)["lo"] is not None else -99)
    g = grade(best)
    good = g["grade"] in want
    units = ", ".join(sorted({L.unit for L in Ls}))
    where = best.sigungu or best.sido or best.region
    sched = (f"특별공급 {_md(best.special_apply)} · 접수 {_md(best.apply)}" if best.special_apply and best.special_apply != best.apply
             else f"접수 {_md(best.apply)}")
    return (f"{'[' + g['name'] + '] ' if good else ''}{best.name} ({where}) {units} · {sched}", good)


def build_events(listings: list[Listing], previous_ids: Optional[set[str]], today: date, cfg: dict,
                 reminders: bool = True) -> tuple[list[dict], list[str]]:
    want = set(cfg.get("notify_grades", ["lotto", "consider"]))
    log: list[str] = []
    events: list[dict] = []

    def ev(kind: str, Ls: list[Listing]) -> dict:
        line, good = _line(Ls, want)
        L = Ls[0]
        return {"kind": kind, "sido": L.sido or (L.region if L.region != "지방" else None), "good": good,
                "name": L.name, "line": line, "url": f"/#/detail/{L.id}"}

    if previous_ids is None:
        log.append("[알림·웹푸시] 지난 결과가 없어 '새 공고' 알림은 건너뜀 (첫 실행)")
    else:
        seen = {i.split("-")[0] for i in previous_ids}     # 공고 단위로 비교 (같은 공고의 주택형이 나중에 늘어도 '새 공고'로 보지 않음)
        fresh = [L for L in listings if L.id.split("-")[0] not in seen and (L.apply_end or L.apply or "9999") >= today.isoformat()]
        groups = _groups(fresh)
        if len(groups) > MAX_NEW:
            log.append(f"[경고] 웹푸시: 새 공고가 {len(groups)}건이라 비교 기준이 비정상으로 보여 '새 공고' 알림을 보내지 않음")
        else:
            events += [ev("new", Ls) for Ls in groups.values()]

    if reminders:
        soon = (today + timedelta(days=int(cfg.get("remind_days_before", 1)))).isoformat()
        for nid, Ls in _groups(listings).items():
            L = Ls[0]
            if _first_day(L) == soon:
                events.append(ev("start", Ls))
            elif L.apply_end == soon and _first_day(L) != soon:
                events.append(ev("end", Ls))
    else:
        log.append("[알림·웹푸시] 코드 변경으로 돈 실행이라 접수 전날 알림은 건너뜀 (매일 새벽 실행에서만 보냄)")
    return events, log


def send(events: list[dict], api: str, token: str, client: Optional[httpx.Client] = None) -> list[str]:
    if not events:
        return ["[알림·웹푸시] 보낼 이벤트 없음"]
    http = client or httpx.Client(timeout=30)
    tot = {"seen": 0, "sent": 0, "none": 0, "gone": 0, "failed": 0}
    cursor, calls = None, 0
    try:
        while calls < MAX_CALLS:
            r = http.post(api.rstrip("/") + "/send", json={"events": events, "cursor": cursor},
                          headers={"Authorization": f"Bearer {token}"})
            calls += 1
            if r.status_code != 200:
                return [f"[경고] 웹푸시 발송 실패: 알림 서버 응답 {r.status_code} (호출 {calls}번째)"]
            j = r.json()
            for k in tot:
                tot[k] += int(j.get(k, 0))
            cursor = j.get("next")
            if not cursor:
                break
    except Exception as e:
        return [f"[경고] 웹푸시 발송 실패: {e}"]
    kinds = {k: sum(1 for e in events if e["kind"] == k) for k in ("new", "start", "end")}
    line = (f"[알림·웹푸시] 이벤트 새 공고 {kinds['new']}·내일 시작 {kinds['start']}·내일 마감 {kinds['end']} → "
            f"구독 {tot['seen']}명 중 보냄 {tot['sent']} · 해당 없음 {tot['none']} · 만료 삭제 {tot['gone']} · 실패 {tot['failed']}")
    return [line] + ([f"[경고] 웹푸시 {tot['failed']}건 실패"] if tot["failed"] else [])


def run(listings: list[Listing], previous_ids: Optional[set[str]], today: date, cfg: dict) -> list[str]:
    api, token = cfg.get("push_api"), os.environ.get("PUSH_SEND_TOKEN")
    reminders = os.environ.get("GITHUB_EVENT_NAME", "schedule") != "push"
    events, log = build_events(listings, previous_ids, today, cfg, reminders)
    if not api:
        return log + [f"[알림·웹푸시] 알림 서버 주소(push_api)가 없어 보내지 않음 · 이벤트 {len(events)}건"]
    if not token:
        return log + [f"[알림·웹푸시] 발송 토큰(PUSH_SEND_TOKEN)이 없어 보내지 않음 · 이벤트 {len(events)}건"]
    return log + send(events, api, token)
