"""청약 경쟁률 · 당첨 가점 (한국부동산원 청약홈 청약접수 경쟁률 및 특별공급 신청현황 조회 서비스).

    https://api.odcloud.kr/api/ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancCmpet    APT 경쟁률
    https://api.odcloud.kr/api/ApplyhomeInfoCmpetRtSvc/v1/getRemndrLttotPblancCmpet 무순위·잔여세대 경쟁률
    https://api.odcloud.kr/api/ApplyhomeInfoCmpetRtSvc/v1/getAptLttotPblancScore    APT 당첨 가점

공공데이터포털 활용신청(2026-09-30)이 필요하고, 인증키는 DATA_GO_KR_KEY 를 그대로 쓴다.
응답 필드 이름은 실행 기록의 [응답 필드] 경쟁률·당첨가점 줄로 확인한다 (아래 FIELD 는 후보 목록).
"""
from __future__ import annotations

from typing import Optional

import httpx

BASE = "https://api.odcloud.kr/api/ApplyhomeInfoCmpetRtSvc/v1"
PATHS = {
    "general": "/getAPTLttotPblancCmpet",
    "remainder": "/getRemndrLttotPblancCmpet",
    "score": "/getAptLttotPblancScore",
}
SOURCE_URL = "https://www.data.go.kr/data/15098905/openapi.do"
FIELD = {
    "house_ty": ["HOUSE_TY"],
    "rank": ["SUBSCRPT_RANK_CODE"],
    "reside": ["RESIDE_SENM", "RESIDE_SECD"],
    "supply": ["SUPLY_HSHLDCO"],
    "req": ["REQ_CNT"],
    "rate": ["CMPET_RATE"],
    "low": ["LWET_SCORE"],
    "top": ["TOP_SCORE"],
    "avg": ["AVRG_SCORE"],
}
RAW_KEYS: dict[str, list[str]] = {}
SAMPLES: dict[str, dict] = {}


def _pick(row: dict, key: str):
    for k in FIELD[key]:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return None


def _num(v) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


class CmpetClient:
    def __init__(self, key: str, http: Optional[httpx.Client] = None):
        self.key = key
        self.http = http or httpx.Client(timeout=20)

    def rows(self, kind: str, manage_no: str) -> list[dict]:
        r = self.http.get(BASE + PATHS[kind], params={"page": 1, "perPage": 500, "returnType": "JSON", "serviceKey": self.key,
                                                      "cond[HOUSE_MANAGE_NO::EQ]": manage_no})
        if r.status_code in (401, 403):
            raise PermissionError(f"응답 {r.status_code} (활용신청·승인 확인 필요)")
        r.raise_for_status()
        data = r.json().get("data") or []
        name = {"general": "경쟁률(APT)", "remainder": "경쟁률(무순위)", "score": "당첨가점"}[kind]
        if data:
            RAW_KEYS.setdefault(name, sorted(data[0].keys()))
            SAMPLES.setdefault(name, data[0])
        return data


def parse(cmpet_rows: list[dict], score_rows: list[dict]) -> dict[str, dict]:
    """주택형(HOUSE_TY)별 {rows:[순위·지역별 공급·접수·경쟁률], scores:[지역별 당첨가점]}."""
    out: dict[str, dict] = {}
    for r in cmpet_rows:
        ty = str(_pick(r, "house_ty") or "").strip()
        if not ty:
            continue
        out.setdefault(ty, {"rows": [], "scores": []})["rows"].append({
            "rank": str(_pick(r, "rank") or ""), "reside": str(_pick(r, "reside") or ""),
            "supply": _num(_pick(r, "supply")), "req": _num(_pick(r, "req")),
            "rate": str(_pick(r, "rate") or "").strip(), "rate_num": _num(_pick(r, "rate")),
        })
    for r in score_rows:
        ty = str(_pick(r, "house_ty") or "").strip()
        if not ty:
            continue
        out.setdefault(ty, {"rows": [], "scores": []})["scores"].append({
            "reside": str(_pick(r, "reside") or ""),
            "low": _num(_pick(r, "low")), "top": _num(_pick(r, "top")), "avg": _num(_pick(r, "avg")),
        })
    return out


def headline(comp: Optional[dict]) -> Optional[dict]:
    """목록에 보여줄 대표 경쟁률: 1순위 해당지역 → 1순위 아무 지역 → 첫 줄."""
    if not comp or not comp.get("rows"):
        return None
    rows = comp["rows"]
    first = [r for r in rows if r["rank"] in ("1", "01", "1순위")]
    local = [r for r in first if "해당" in r["reside"]]
    return (local or first or rows)[0]


def apply_competition(listings: list, log: list[str], today: str, client: Optional[CmpetClient] = None) -> None:
    """접수가 시작된 공고의 경쟁률·당첨가점을 주택형에 붙인다. 공고당 한 번 조회."""
    import os
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key and client is None:
        log.append("[경쟁률] 인증키가 없어 건너뛰었어요")
        return
    cl = client or CmpetClient(key)
    groups: dict[str, list] = {}
    for L in listings:
        started = L.apply or L.special_apply
        if started and started <= today:
            groups.setdefault(L.id.split("-")[0], []).append(L)
    got = 0
    for nid, Ls in groups.items():
        kind = "remainder" if Ls[0].category == "remainder" else "general"
        try:
            c = cl.rows(kind, nid)
            s = cl.rows("score", nid) if kind == "general" else []
        except Exception as e:
            log.append(f"[경쟁률] {Ls[0].name}: 조회 실패 ({e})")
            continue
        by_ty = parse(c, s)
        n = 0
        for L in Ls:
            ty = L.id.split("-", 1)[1]
            comp = by_ty.get(ty)
            if comp and (comp["rows"] or comp["scores"]):
                L.competition = comp
                n += 1
        got += bool(n)
        h = headline(by_ty.get(Ls[0].id.split("-", 1)[1]))
        log.append(f"[경쟁률] {Ls[0].name}: 경쟁률 {len(c)}줄 · 가점 {len(s)}줄 → 주택형 {n}/{len(Ls)}개에 반영"
                   + (f" (예: {Ls[0].unit} {h['rank']}순위 {h['reside']} 공급 {h['supply']} 접수 {h['req']} 경쟁률 {h['rate']})" if h else ""))
    log.append(f"[경쟁률] 접수가 시작된 공고 {len(groups)}건 중 {got}건에 결과가 있어요")
    for name, keys in RAW_KEYS.items():
        log.append(f"[응답 필드] {name}: {', '.join(keys)}")
    for name, row in SAMPLES.items():
        log.append(f"[응답 예시] {name}: " + ", ".join(f"{k}={v}" for k, v in row.items()))


# ── 신청 전 참고: 같은 시·군·구의 지난 청약 결과 ─────────────────────────────
# 공고별 결과를 docs/cmpet-history.json 에 쌓아 두고(한 번 받은 결과는 다시 받지 않음),
# 접수 전·접수 중 공고에 '같은 시·군·구, 최근 12개월, 비슷한 면적' 단지의 1순위 경쟁률·당첨 가점을 붙인다.
import json as _json
from datetime import date as _date, timedelta as _td
from pathlib import Path as _Path

HISTORY = _Path(__file__).resolve().parent.parent.parent / "docs" / "cmpet-history.json"
HISTORY_MONTHS = 12
HISTORY_BUDGET_SEC = 180
EMPTY_RETRY_DAYS = 30      # 결과가 비어 있던 공고는 30일 뒤에 다시 확인
AREA_TOL = 15.0            # 전용면적 차이 허용 (㎡)


def load_history(path: _Path = None) -> dict:
    try:
        return _json.loads((path or HISTORY).read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_history(h: dict, path: _Path = None) -> None:
    (path or HISTORY).write_text(_json.dumps(h, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def summarize(by_ty: dict[str, dict]) -> dict[str, dict]:
    """주택형별 대표 결과만 남긴다 (기록 크기를 줄이려고)."""
    from .applyhome import area_of, unit_label
    out = {}
    for ty, comp in by_ty.items():
        h = headline(comp)
        sc = comp.get("scores") or []
        s = next((x for x in sc if "해당" in x["reside"]), sc[0] if sc else None)
        if not h and not s:
            continue
        out[ty] = {"unit": unit_label(ty), "area": area_of(ty),
                   "rank": h and h["rank"], "reside": h and h["reside"], "supply": h and h["supply"], "req": h and h["req"],
                   "rate": h and h["rate"], "rate_num": h and h["rate_num"],
                   "low": s and s["low"], "avg": s and s["avg"], "top": s and s["top"]}
    return out


def update_history(ah, listings: list, log: list[str], today: _date, client: "CmpetClient" = None,
                   history: dict = None) -> dict:
    """현재 공고들의 시·군·구에서 최근 12개월 동안 접수가 끝난 공고의 결과를 기록에 채운다."""
    import os
    import time
    from .. import region as RG
    from .applyhome import pick, to_date
    h = load_history() if history is None else history
    key = os.environ.get("DATA_GO_KR_KEY")
    if client is None and not key:
        log.append("[지난 경쟁률] 인증키가 없어 건너뛰었어요")
        return h
    cl = client or CmpetClient(key)
    sgs = {L.sigungu for L in listings if L.sigungu}
    since = (today - _td(days=31 * HISTORY_MONTHS)).isoformat()
    t0, added, empty, checked = time.monotonic(), 0, 0, 0
    for cat in ("general", "remainder"):
        try:
            notices = ah.notices(cat, since=since)
        except Exception as e:
            log.append(f"[지난 경쟁률] {cat} 공고 목록 실패: {e}")
            continue
        for d in notices:
            no = str(pick(d, "manage_no") or pick(d, "notice_no") or "")
            addr = pick(d, "address") or ""
            sg = RG.sigungu_of(addr)
            end = to_date(pick(d, "apply_end")) or to_date(pick(d, "apply"))
            if not no or sg not in sgs or not end or end >= today.isoformat():
                continue
            old = h.get(no)
            if old and (old.get("units") or old.get("checked", "") > (today - _td(days=EMPTY_RETRY_DAYS)).isoformat()):
                continue
            if time.monotonic() - t0 > HISTORY_BUDGET_SEC:
                break
            try:
                kind = "remainder" if cat == "remainder" else "general"
                units = summarize(parse(cl.rows(kind, no), cl.rows("score", no) if kind == "general" else []))
            except Exception as e:
                log.append(f"[지난 경쟁률] {pick(d, 'name')}: 조회 실패 ({e})")
                continue
            checked += 1
            h[no] = {"name": pick(d, "name") or "", "address": addr, "sigungu": sg, "sido": RG.sido_of(addr),
                     "category": cat, "notice": to_date(pick(d, "notice")), "apply": to_date(pick(d, "apply")),
                     "url": pick(d, "url"), "units": units, "checked": today.isoformat()}
            added += bool(units)
            empty += not units
    # 오래된 기록 정리
    for no in [k for k, v in h.items() if (v.get("apply") or "") < since]:
        del h[no]
    log.append(f"[지난 경쟁률] 시·군·구 {len(sgs)}곳 · 이번에 {checked}건 조회 (결과 있음 {added}, 비어 있음 {empty}) · 기록 {len(h)}건 · "
               f"{time.monotonic() - t0:.0f}초")
    return h


def attach_area_comps(listings: list, history: dict, today: _date, limit: int = 3) -> None:
    """자기 결과가 없는 공고에 같은 시·군·구의 최근 결과(비슷한 면적)를 최신순으로 붙인다."""
    since = (today - _td(days=31 * HISTORY_MONTHS)).isoformat()
    for L in listings:
        if L.competition or not L.sigungu:
            L.area_comps = None if L.competition else []
            continue
        own = L.id.split("-")[0]
        found = []
        for no, e in history.items():
            if no == own or e.get("sigungu") != L.sigungu or (e.get("apply") or "") < since or not e.get("units"):
                continue
            us = [u for u in e["units"].values() if u.get("area") and L.area and abs(u["area"] - L.area) <= AREA_TOL
                  and (u.get("rate") or u.get("low") is not None)]
            if not us:
                continue
            u = min(us, key=lambda u: abs(u["area"] - L.area))
            found.append({"name": e["name"], "notice": e.get("notice"), "apply": e.get("apply"), "url": e.get("url"),
                          "category": e.get("category"), **{k: u.get(k) for k in
                          ("unit", "area", "rank", "reside", "supply", "req", "rate", "rate_num", "low", "avg")}})
        found.sort(key=lambda x: x.get("apply") or "", reverse=True)
        L.area_comps = found[:limit]
