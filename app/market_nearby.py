"""시세 비교를 '같은 구' 대신 '가까운 곳'부터 (기능 market_nearby, 2026-10-28 운영자 요청).

문제: 같은 구 신축 같은 평형 매매(district_newbuild)는 구 안 동네 차이를 못 본다 — 분당하이스트(정자동)가 대장동·백현동 거래로,
트리븐센텀(반여동) 115㎡가 해운대 바닷가 큰 평형 거래로 잡혔다.

순서 (앞 단계 거래가 NEARBY_MIN(5건) 이상이면 거기서 멈춘다):
  ① 같은 단지 — app/market.estimate_market 가 이미 잡으면(same_complex·same_complex_ppa) 그대로 둔다
  ② 같은 법정동 (공고 주소의 동·읍·면 = 거래 umdNm 첫 낱말) — 공고에서 2km 넘는 단지는 뺌(2026-10-28 운영자, 큰 법정동 대비)
  ③ 공고 좌표에서 반경 1km → 1.5km → 2km (거래 단지 좌표: 지번으로 한 번 찾아 evidence/market/complex-geo.json 에 저장, 못 찾은 단지는 뺌)
  ③-1 어느 단계도 5건이 안 되면 가장 가까운 단계의 3~4건으로 '추정' (근거 끝에 _few, 문구 '가까운 거래가 N건뿐이라 추정이에요')
  ④ 같은 구 — estimate_market 결과 그대로 (가까운 거래가 2건 이하일 때만)
면적 기준은 ④에서 쓴 규칙을 그대로 쓴다: 같은 평형(±3㎡) / 비슷한 면적(±10㎡) ㎡당 / 100㎡ 이상 ㎡당. 모두 준공 10년 이내·직거래 뺌.
기준 시세 = 중앙값, 보수 시세 = 하위 25% (app/market 과 같은 계산).
반경은 같은 시군구 거래만 본다(실거래가는 시군구 단위로 받음 — 구 경계 너머 단지는 들어가지 않음).
"""
from __future__ import annotations

import json
import math
import re
import statistics
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from . import rules as R
from .market import _comp, _in_band, _p25, _recent, _summary, dong_of

ROOT = Path(__file__).resolve().parents[1]
COORD_CACHE = ROOT / "evidence" / "market" / "complex-geo.json"
RULE = {"district_newbuild": "newbuild", "district_area_ppa": "area_ppa", "district_large_ppa": "large_ppa"}
RETRY_NONE_DAYS = 30
GEO_BUDGET_SEC = 150


def dist_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lng2 - lng1) * p / 2) ** 2
    return int(round(12742000 * math.asin(math.sqrt(a))))


def complex_key(lawd: str, r: dict) -> Optional[str]:
    """거래 단지 하나를 가리키는 열쇠 (시군구 코드 | 법정동 | 지번). 지번이 없으면 좌표를 찾을 수 없어 None"""
    j = str(r.get("jibun") or "").strip()
    if not j or not r.get("umd"):
        return None
    return f"{lawd}|{r['umd'].strip()}|{j}"


def address_prefix(address: str) -> str:
    """공고 주소의 시·도 + 시·군·구 ('경기도 성남시 분당구 정자동 90번지' → '경기도 성남시 분당구')"""
    out = []
    for t in (address or "").split():
        if re.fullmatch(r"[가-힣]+[0-9]?(?:동|읍|면|가|리)", t) and out and t != "공동":
            break
        if re.search(r"\d", t):
            break
        out.append(t)
    return " ".join(out)


def _newbuild(r: dict, this_year: int) -> bool:
    return bool(r.get("build_year")) and r["build_year"] >= this_year - R.NEW_BUILD_YEARS


def rule_pool(trades: list[dict], area: Optional[float], rule: str, this_year: int) -> list[dict]:
    """④(같은 구)에서 쓴 면적 규칙 그대로 고른 거래 (직거래 포함 — 호출하는 쪽이 나눈다)"""
    if not area:
        return []
    def fit(r):
        if not (r.get("amount") and r.get("area") and _newbuild(r, this_year)):
            return False
        if rule == "newbuild":
            return _in_band(r["area"], area)
        if rule == "area_ppa":
            return abs(r["area"] - area) <= R.AREA_BAND_WIDE
        return r["area"] >= R.LARGE_AREA
    return [r for r in trades if fit(r)]


def _result(rows: list[dict], direct: int, area: float, rule: str, stage: str, scope: str, dists: Optional[dict] = None, few: bool = False) -> dict:
    """few: 가까운 거래가 NEARBY_FEW~NEARBY_MIN-1(3~4)건이라 그 거래로 '추정' (2026-10-28 운영자: 같은 구로 돌아가지 말고 추정 표시)"""
    basis = f"{stage}_{rule}"
    comps = []
    for r in rows:
        c = _comp(r, "매매", "amount")
        if dists is not None and id(r) in dists:
            c["m"] = dists[id(r)]
        comps.append(c)
    head = f"가까운 거래가 {len(rows)}건뿐이라 추정이에요 — " if few else ""
    if rule == "newbuild":
        low, base = _summary([r["amount"] for r in rows])
        note = f"{head}{scope} 준공 {R.NEW_BUILD_YEARS}년 이내 같은 평형({int(area)}㎡) 매매 {len(rows)}건 기준 (최근 {R.MARKET_MONTHS}개월)"
    else:
        ppa = [r["amount"] / r["area"] for r in rows]
        base = statistics.median(ppa) * area / 10000
        low = round(_p25(ppa) * area / 10000 if len(ppa) >= 4 else base * R.LOW_DISCOUNT, 2)   # app/market 과 같게 반올림 전 값으로
        base = round(base, 2)
        if rule == "area_ppa":
            note = (f"{head}같은 평형 거래가 부족해 {scope} 준공 {R.NEW_BUILD_YEARS}년 이내 비슷한 면적(±{R.AREA_BAND_WIDE:g}㎡) 매매 {len(rows)}건의 "
                    f"㎡당 가격 × 전용 {area:.1f}㎡로 추정 (최근 {R.MARKET_MONTHS}개월)")
        else:
            note = (f"{head}이 면적대 거래가 없어 {scope} 준공 {R.NEW_BUILD_YEARS}년 이내 전용 {R.LARGE_AREA:g}㎡ 이상 매매 {len(rows)}건의 "
                    f"㎡당 가격 × 전용 {area:.1f}㎡로 추정 (최근 {R.MARKET_MONTHS}개월)")
    out = {"mkt_low": low, "mkt_base": base, "mkt_basis": basis, "mkt_count": len(rows), "mkt_comps": _recent(comps),
           "mkt_direct_excluded": direct, "mkt_note": note}
    if few:
        out["mkt_basis"] = basis + "_few"
    return out


def needed_keys(lawd: str, trades: list[dict], area: Optional[float], basis: Optional[str], this_year: int) -> set:
    """같은 동 거리 확인·반경 비교에 좌표가 필요한 단지 열쇠 (④에서 쓴 규칙의 같은 구 후보 단지 전부)"""
    rule = RULE.get(basis or "")
    if not rule:
        return set()
    return {k for r in rule_pool(trades, area, rule, this_year) if r.get("deal_type") != "직거래" for k in [complex_key(lawd, r)] if k}


def estimate_nearby(address: str, area: Optional[float], basis: Optional[str], trades: list[dict], this_year: int,
                    origin: Optional[dict], coords: dict, lawd: str) -> tuple[Optional[dict], dict]:
    """(새 시세 또는 None(④ 같은 구 그대로), 단계별 건수 기록).
    coords: 단지 열쇠 → {'lat','lng'} 또는 {'none': 사유}. 후보 단지 중 아직 찾아보지 않은 곳이 있으면 비교하지 않는다(일부만 찾은 채 비교하지 않게).
    2026-10-28 운영자 결정: ① 같은 동이어도 공고에서 NEARBY_RADII 최대(2km)보다 먼 단지는 뺀다(고양 장항동 → 킨텍스원시티)
                          ② 어느 단계도 5건이 안 되면 같은 구로 돌아가지 않고 가장 가까운 단계의 3~4건으로 '추정'(mkt_basis 끝 _few)
    좌표를 못 찾은 단지(지번 없음·지오코딩 실패)는 같은 동 단계에서는 남기고(거리 모름), 반경 단계에서는 뺀다."""
    info: dict = {"rule": RULE.get(basis or ""), "dong": dong_of(address), "steps": []}
    rule = info["rule"]
    if not rule or not area:
        return None, info
    pool = rule_pool(trades, area, rule, this_year)
    live = [r for r in pool if r.get("deal_type") != "직거래"]
    direct = lambda rows: sum(1 for r in rows if r.get("deal_type") == "직거래")
    dong = info["dong"]
    has_origin = bool(origin) and origin.get("lat") is not None
    dists: dict = {}
    if has_origin:
        keys = {complex_key(lawd, r) for r in live}
        pending = sorted(k for k in keys if k and k not in coords)
        if pending:
            info["steps"].append(("near", f"단지 좌표 확인 중 {len(pending)}곳"))
            return None, info
        info["no_coord"] = sum(1 for r in live if not complex_key(lawd, r) or "lat" not in coords.get(complex_key(lawd, r), {}))
        for r in pool:
            c = coords.get(complex_key(lawd, r) or "", {})
            if "lat" in c:
                dists[id(r)] = dist_m(origin["lat"], origin["lng"], c["lat"], c["lng"])
    far = max(R.NEARBY_RADII)
    rough = has_origin and origin.get("precision") != "exact"
    where = "(공고 주소가 동까지만 있어 동 중심에서 잰 거리)" if rough else ""
    tiers = []   # (단계, 고른 거래(직거래 포함), 범위 글)
    if dong:
        mine = [r for r in pool if (r.get("umd") or "").split()[:1] == [dong] and dists.get(id(r), 0) <= far]
        tiers.append(("dong", mine, f"같은 동({dong})" + (f" {far / 1000:g}km 안" if has_origin else "")))
    if has_origin:
        for rad in R.NEARBY_RADII:
            tiers.append((f"r{rad}", [r for r in pool if id(r) in dists and dists[id(r)] <= rad], f"공고 위치 반경 {rad / 1000:g}km 안" + where))
    elif dong:
        info["steps"].append(("near", "공고 좌표 없음"))
    counts = []
    for stage, mine, scope in tiers:
        rows = [r for r in mine if r.get("deal_type") != "직거래"]
        counts.append((stage, rows, mine, scope))
        info["steps"].append((stage, len(rows)))
        if len(rows) >= R.NEARBY_MIN:
            return _result(rows, direct(mine), area, rule, "dong" if stage == "dong" else "near", scope, dists if stage != "dong" else None), info
    for stage, rows, mine, scope in counts:
        if len(rows) >= R.NEARBY_FEW:
            info["few"] = stage
            return _result(rows, direct(mine), area, rule, "dong" if stage == "dong" else "near", scope, dists, few=True), info
    return None, info


# ---- 단지 좌표 (네이버 지오코딩, 한 번 찾으면 저장) ----

def load_coords(path: Path = COORD_CACHE) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_coords(coords: dict, path: Path = COORD_CACHE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(coords, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")


def usable(coords: dict, today: date) -> dict:
    """못 찾은 단지는 RETRY_NONE_DAYS 지나면 다시 찾게 뺀다"""
    cut = (today - timedelta(days=RETRY_NONE_DAYS)).isoformat()
    return {k: v for k, v in coords.items() if "lat" in v or (v.get("date") or "") >= cut}


def geocode_keys(keys: list[str], prefix_of: dict, sido_of: dict, coords: dict, today: date, log: list, http=None, key=None,
                 budget: float = GEO_BUDGET_SEC) -> int:
    """좌표가 없는 단지를 지번 주소로 찾는다. 정확(지번)으로 찾은 것만 쓰고, 동 중심 결과·시도 다름은 '못 찾음'. 반환: 새로 찾은 수"""
    from . import geo as G
    key = key or G.keys()
    if not key or not keys:
        return 0
    import httpx
    http = http or httpx.Client(timeout=15)
    start, n = time.monotonic(), 0
    for k in keys:
        if time.monotonic() - start > budget:
            log.append(f"[시세·가까운 곳] 단지 좌표 시간 제한 — 남은 {len(keys) - n}곳은 다음 수집에서")
            break
        lawd, umd, jibun = k.split("|", 2)
        addr = f"{prefix_of.get(lawd, '')} {umd} {jibun}".strip()
        try:
            g, msg = G.geocode(addr, sido_of.get(lawd), http, key)
        except Exception as e:
            g, msg = None, f"오류 {e.__class__.__name__}"
        if g and g.get("precision") == "exact":
            coords[k] = {"lat": g["lat"], "lng": g["lng"], "matched": g.get("matched"), "date": today.isoformat()}
        else:
            coords[k] = {"none": (msg or "못 찾음")[:80] if not g else "지번으로 못 찾고 동 중심만 나옴", "date": today.isoformat()}
        n += 1
    return n


def apply(out: list, rt, today: date, lawd_cache: dict, log: list, http=None, save: bool = True, coord_path: Path = COORD_CACHE) -> dict:
    """수집 끝(좌표를 붙인 뒤)에 같은 구 기준 시세를 가까운 곳 기준으로 바꾼다. 실거래는 이미 받은 것(rt 캐시)만 쓴다."""
    from . import lawd as LC
    from .market import months_back
    months = months_back(today, R.MARKET_MONTHS)
    all_coords = load_coords(coord_path)
    coords = usable(all_coords, today)
    jobs = []
    for L in out:
        if not RULE.get(L.mkt_basis or "") or getattr(L, "rental", False):
            continue
        lawd = LC.lawd_for(L.address, lawd_cache, L.sido)
        if not lawd:
            continue
        try:
            trades = rt.recent("trade", lawd, months)
        except Exception:
            continue
        jobs.append((L, lawd, trades))
    # 1) 후보 단지 좌표를 먼저 찾는다 (같은 동도 2km 넘는 단지는 빼므로 모두 필요)
    need, prefix_of, sido_of = [], {}, {}
    for L, lawd, trades in jobs:
        if not getattr(L, "geo", None):
            continue   # 공고 좌표가 없으면 같은 동만 본다(거리를 잴 수 없음)
        prefix_of.setdefault(lawd, address_prefix(L.address))
        sido_of.setdefault(lawd, L.sido)
        need += [k for k in sorted(needed_keys(lawd, trades, L.area, L.mkt_basis, today.year)) if k not in coords and k not in need]
    found = geocode_keys(need, prefix_of, sido_of, coords, today, log, http=http)
    all_coords.update(coords)
    if save and found:
        save_coords(all_coords, coord_path)
    # 2) 단계별로 다시 계산
    stat = {"dong": 0, "r1000": 0, "r1500": 0, "r2000": 0, "district": 0, "few": 0}
    for L, lawd, trades in jobs:
        res, info = estimate_nearby(L.address, L.area, L.mkt_basis, trades, today.year, getattr(L, "geo", None), coords, lawd)
        if not res:
            stat["district"] += 1
            continue
        stage = info.get("few") or ("dong" if res["mkt_basis"].startswith("dong_") else next(s for s, n in reversed(info["steps"]) if isinstance(n, int)))
        stat[stage] = stat.get(stage, 0) + 1
        stat["few"] += bool(info.get("few"))
        for k, v in res.items():
            setattr(L, k, v)
    ok = sum(1 for k in coords if "lat" in coords[k])
    log.append(f"[시세·가까운 곳] 주택형 {len(jobs)}개: 같은 동 {stat['dong']} · 반경 1km {stat['r1000']} · 1.5km {stat['r1500']} · 2km {stat['r2000']}"
               f" · 같은 구 그대로 {stat['district']} · 그중 3~4건 추정 {stat['few']} (단지 좌표 {ok}곳, 이번에 새로 찾음 {found}곳)")
    return stat
