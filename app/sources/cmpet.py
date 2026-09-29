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
