"""시세 원자료 대조 (2026-10-02 MASTER QA 남은 일 '시세 원자료 대조').

화면의 시세(mkt_base·mkt_low·mkt_count)와 근거 거래(mkt_comps)가 국토교통부 실거래가 원자료와 같은지, 수집 코드(app/market.py·app/sources/rtms.py)를
쓰지 않고 따로 받아·따로 계산해 비교한다.
  - 원자료: 아파트 매매(RTMSDataSvcAptTrade)·분양권 전매(RTMSDataSvcSilvTrade) XML 을 이 파일에서 직접 받아 읽는다.
  - 규칙(app/market.py 머리말과 같은 뜻을 따로 구현): 해제 거래(cdealType O)·직거래 제외 → 같은 단지(이름 포함 관계)·같은 평형(전용 ±3㎡) 거래가 있으면 그것,
    없으면 같은 시군구 준공 10년 이내 같은 평형 매매 3건 이상. 기준 = 중앙값, 보수 = 하위 25%(4건 미만이면 기준 × 0.9). 최근 6개월.
  - 근거 거래 한 건 한 건이 원자료에 같은 단지·면적·층·금액·날짜로 있는지 본다.
매 수집 뒤 공고 몇 개씩 돌아가며 본다(요청 수를 줄이려고). 인증키(DATA_GO_KR_KEY)가 없으면 건너뛴다 — 키는 Actions 비밀값에만 있다.
사용: python -m tools.qa.market_check [--n 8] [--date YYYY-MM-DD] → evidence/qa/market-check.json, 다르면 종료 코드 1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence" / "qa" / "market-check.json"
BASE = "https://apis.data.go.kr/1613000"
EP = {"trade": "/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade", "presale": "/RTMSDataSvcSilvTrade/getRTMSDataSvcSilvTrade"}
MONTHS, BAND, NEW_YEARS, LOW_X = 6, 3.0, 10, 0.90
WIDE, WIDE_MIN = 10.0, 5   # 기능 mkt_area_fallback (app/rules.py AREA_BAND_WIDE·AREA_FALLBACK_MIN 과 같은 값, 따로 적음)


def months(today: date, n: int = MONTHS) -> list[str]:
    y, m, out = today.year, today.month, []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out


def num(v):
    s = re.sub(r"[^0-9.\-]", "", v or "")
    return float(s) if s else None


def rows_of(xml_text: str) -> list[dict]:
    """원자료 한 쪽 → 거래 목록 (해제·직거래 표시는 그대로 두고 판단은 아래에서)"""
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter("item"):
        g = {c.tag: (c.text or "").strip() for c in it}
        out.append({"apt": g.get("aptNm", ""), "area": num(g.get("excluUseAr")), "floor": num(g.get("floor")), "amount": num(g.get("dealAmount")),
                    "build": num(g.get("buildYear")), "cancel": g.get("cdealType", "").upper() == "O", "direct": g.get("dealingGbn", "") == "직거래",
                    "date": f"{g.get('dealYear', '')}-{g.get('dealMonth', '').zfill(2)}-{g.get('dealDay', '').zfill(2)}"})
    return out


def flat(s: str) -> str:
    return re.sub(r"[\s()·\-]|아파트", "", s or "")


def p25(xs: list[float]) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) / 4
    i = int(k)
    j = min(i + 1, len(xs) - 1)
    return xs[i] + (xs[j] - xs[i]) * (k - i)


def expect(name: str, area: float, trades: list[dict], presales: list[dict], year: int, fallback: bool = False) -> dict:
    """원자료로 따로 계산한 시세 (억 원, 소수 둘째 자리)"""
    live = lambda r: not r["cancel"] and not r["direct"] and r["amount"]
    band = lambda r: r["area"] is not None and area is not None and abs(r["area"] - area) <= BAND
    n = flat(name)
    same = lambda r: bool(flat(r["apt"])) and bool(n) and (flat(r["apt"]) in n or n in flat(r["apt"]))
    own = [r for r in presales + trades if live(r) and band(r) and same(r)]
    pool, basis = (own, "same_complex") if own else ([r for r in trades if live(r) and band(r) and r["build"] and r["build"] >= year - NEW_YEARS], "district_newbuild")
    if basis == "district_newbuild" and len(pool) < 3:
        # 기능 mkt_area_fallback: ±10㎡ 같은 구 신축 매매 5건 이상이면 ㎡당 가격(중앙값·하위 25%) × 면적 — 수집 코드와 따로 옮긴 계산
        wide = [r for r in trades if fallback and area and live(r) and r["area"] and abs(r["area"] - area) <= WIDE and r["build"] and r["build"] >= year - NEW_YEARS]
        if len(wide) >= WIDE_MIN:
            u = sorted(r["amount"] / r["area"] for r in wide)
            base = statistics.median(u) * area / 10000
            low = p25(u) * area / 10000 if len(u) >= 4 else base * LOW_X
            return {"basis": "district_area_ppa", "count": len(wide), "base": round(base, 2), "low": round(low, 2), "rows": wide}
        return {"basis": None, "count": len(pool), "base": None, "low": None, "rows": pool}
    a = [r["amount"] for r in pool]
    base = statistics.median(a) / 10000
    low = p25(a) / 10000 if len(a) >= 4 else base * LOW_X
    return {"basis": basis, "count": len(pool), "base": round(base, 2), "low": round(low, 2), "rows": pool}


def comp_in(c: dict, rows: list[dict]) -> bool:
    return any(r["apt"] == c.get("apt") and r["date"] == c.get("date") and r["area"] == c.get("area") and r["floor"] == c.get("floor")
               and abs((r["amount"] or 0) / 10000 - (c.get("amount") or 0)) < 0.006 for r in rows)


def fetch(http, key: str, kind: str, lawd: str, ym: str) -> list[dict]:
    out = []
    for page in range(1, 20):
        r = http.get(BASE + EP[kind], params={"serviceKey": key, "LAWD_CD": lawd, "DEAL_YMD": ym, "numOfRows": 1000, "pageNo": page})
        r.raise_for_status()
        rows = rows_of(r.text)
        out += rows
        if len(rows) < 1000:
            break
    return out


def check(listings: list[dict], today: date, get, fallback: bool | None = None) -> dict:
    """get(kind, lawd, ym) → 원자료 거래 목록. 공고마다 시세·근거 거래를 원자료와 비교"""
    from app import lawd as LC
    cache, res = LC.load(), []
    if fallback is None:   # 수집과 같은 스위치(docs/config.json features.mkt_area_fallback, 없으면 켜짐)
        try:
            fallback = json.loads((ROOT / "docs" / "config.json").read_text(encoding="utf-8")).get("features", {}).get("mkt_area_fallback", True) is not False
        except Exception:
            fallback = True
    for L in listings:
        lawd = LC.lawd_for(L.get("address") or "", cache, L.get("sido"))
        if not lawd:
            res.append({"id": L["id"], "skip": "법정동 코드 없음"})
            continue
        tr = [r for ym in months(today) for r in get("trade", lawd, ym)]
        ps = [r for ym in months(today) for r in get("presale", lawd, ym)]
        e = expect(L["name"], L.get("area"), tr, ps, today.year, fallback=fallback)
        bad = []
        if (L.get("mkt_basis") or None) != e["basis"]:
            bad.append(f"근거 종류 {L.get('mkt_basis')} ≠ 원자료 {e['basis']}")
        for k, v in (("mkt_base", e["base"]), ("mkt_low", e["low"])):
            if L.get(k) != v:
                bad.append(f"{k} {L.get(k)} ≠ 원자료 {v}")
        if e["basis"] and L.get("mkt_count") != e["count"]:
            bad.append(f"거래 수 {L.get('mkt_count')} ≠ 원자료 {e['count']}")
        missing = [c for c in (L.get("mkt_comps") or []) if not comp_in(c, e["rows"])]
        if missing:
            bad.append(f"근거 거래 {len(missing)}건이 원자료(해제·직거래 뺀 같은 조건)에 없음: " + ", ".join(f"{c.get('apt')} {c.get('date')} {c.get('amount')}억" for c in missing[:3]))
        res.append({"id": L["id"], "name": L["name"], "lawd": lawd, "app": {k: L.get(k) for k in ("mkt_basis", "mkt_base", "mkt_low", "mkt_count")},
                    "raw": {k: e[k] for k in ("basis", "base", "low", "count")}, "comps": len(L.get("mkt_comps") or []), "bad": bad})
    return {"date": today.isoformat(), "checked": sum(1 for r in res if "skip" not in r), "fails": sum(1 for r in res if r.get("bad")),
            "comps_checked": sum(r.get("comps", 0) for r in res), "items": res}


def pick(listings: list[dict], today: date, n: int) -> list[dict]:
    """시세가 있는 일반 공고(임대 제외)를 날마다 n개씩 돌아가며"""
    xs = sorted((L for L in listings if L.get("mkt_comps") and not L.get("rental") and not L.get("sample")), key=lambda L: L["id"])
    if not xs:
        return []
    s = (today.toordinal() * n) % len(xs)
    return [xs[(s + k) % len(xs)] for k in range(min(n, len(xs)))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--date")
    a = ap.parse_args()
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        print("[QA 시세 원자료] 인증키 없음 — 건너뜀 (Actions 에서만 돈다)")
        return 0
    import httpx
    sys.path.insert(0, str(ROOT))
    today = date.fromisoformat(a.date) if a.date else date.today()
    data = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    listings = data["items"] if isinstance(data, dict) else data
    http, memo = httpx.Client(timeout=httpx.Timeout(20, connect=10)), {}

    def get(kind, lawd, ym):
        k = (kind, lawd, ym)
        if k not in memo:
            memo[k] = fetch(http, key, kind, lawd, ym)
        return memo[k]

    try:
        r = check(pick(listings, today, a.n), today, get)
    except Exception as e:   # 원자료를 못 받으면 '다름'이 아니라 '확인 못 함'으로 남긴다 (키·주소는 기록하지 않음)
        msg = re.sub(r"(serviceKey=)[^&\s']+", r"\1***", f"{type(e).__name__}: {e}")[:160]
        print(f"[QA 시세 원자료] 원자료를 받지 못함 — {msg}")
        return 0
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[QA 시세 원자료] 공고 {r['checked']}개 · 근거 거래 {r['comps_checked']}건을 국토부 원자료와 대조 · 다름 {r['fails']}건")
    for x in r["items"]:
        for b in x.get("bad") or []:
            print("  ", x["id"], x["name"][:16], "|", b)
    return 1 if r["fails"] else 0


if __name__ == "__main__":
    sys.exit(main())
