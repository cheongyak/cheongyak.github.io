"""시세·전세 추정.

순서:
1. 같은 단지 분양권 전매·매매 거래 (단지명 일치) — 가장 믿을 만함
2. 같은 시군구, 준공 10년 이내, 같은 평형(전용 ±3㎡) 매매 거래
기준 시세 = 중앙값, 보수 시세 = 하위 25% (거래 4건 미만이면 기준 × 0.9)
전세 = 같은 조건 전세(월세 0) 보증금 중앙값 × 입주장 할인
"""
from __future__ import annotations

import re
import statistics
from datetime import date
from typing import Optional

from . import rules as R


def months_back(today: date, n: int) -> list[str]:
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def _norm(s: str) -> str:
    return re.sub(r"[\s()·\-]|아파트", "", s or "")


def dong_of(address: str) -> str:
    """공고 주소의 법정동·읍·면 ('경상남도 거제시 옥포동 1670번지' → '옥포동'). 도로명 주소·지구 이름뿐이면 빈 글자"""
    for t in (address or "").split()[1:5]:
        if re.fullmatch(r"[가-힣]+[0-9]?(?:동|읍|면|가)", t) and t != "공동":
            return t
        if re.search(r"\d", t):
            break
    return ""


def same_complex(apt: str, name: str, umd: str = "", dong: str = "") -> bool:
    """단지 이름이 서로 포함 관계. 거래 법정동과 공고 주소 동·읍·면을 둘 다 알면 같아야 한다
    (2026-10-15: '힐스테이트 거제시그니처'(옥포동)에 상동동 '힐스테이트거제', '이도이동 아이린8차'에 삼도이동 '아이린'이 붙던 문제)"""
    a, n = _norm(apt), _norm(name)
    if not a or not n:
        return False
    if dong and umd and umd.split()[0] != dong:
        return False
    return a in n or n in a


def _in_band(area: Optional[float], target: Optional[float]) -> bool:
    return area is not None and target is not None and abs(area - target) <= R.AREA_BAND


def _p25(xs: list[float]) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * 0.25
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


# 한 단지가 비교 거래를 독차지하지 않게 (기능 market_complex_balance, 2026-10-31 운영자 '한 단지가 거래 독차지 못하게').
# 광교 자연앤 센트레빌 84㎡: 같은 동 2km 안 57건 중 22건이 한 단지(영흥숲 푸르지오 파크비엔, 9억 안팎)라 하위 25%가 그 단지 값이 됐다.
# 규칙: 단지(법정동 + 단지 이름)마다 거래가 COMPLEX_CAP(5)건보다 많으면 그 단지 거래 하나하나의 무게를 5/건수로 줄여, 단지 몫을 최대 5건으로 센다.
# 무게를 붙인 중앙값·하위 25%는 무게가 모두 같으면 지금 계산(_p25 = (n-1)×0.25 자리 보간, statistics.median)과 같다 — 모든 단지가 5건 이하면 결과가 그대로.
# 같은 단지 거래(same_complex)는 한 단지라 그대로. 파이프라인이 스위치에 따라 BALANCE 를 정한다.
BALANCE = False


def complex_id(r: dict) -> str:
    return f"{(r.get('umd') or '').split(' ')[0]}|{_norm(r.get('apt', ''))}"


def _weights(rows: list[dict]) -> list[float]:
    n: dict = {}
    for r in rows:
        n[complex_id(r)] = n.get(complex_id(r), 0) + 1
    return [min(n[complex_id(r)], R.COMPLEX_CAP) / n[complex_id(r)] for r in rows]


def _wq(xs: list[float], ws: list[float], q: float) -> float:
    """무게를 붙인 분위수. 정렬한 값 i 의 자리 = (앞 값들 무게 합) / (전체 무게 − 마지막 값 무게) — 무게가 같으면 i/(n−1) 로 _p25·중앙값과 같다"""
    pr = sorted(zip(xs, ws))
    if len(pr) == 1:
        return pr[0][0]
    den = sum(w for _, w in pr) - pr[-1][1]
    pos, c = [], 0.0
    for _, w in pr:
        pos.append(c / den)
        c += w
    for i in range(len(pr) - 1):
        if pos[i] <= q <= pos[i + 1]:
            t = 0.0 if pos[i + 1] == pos[i] else (q - pos[i]) / (pos[i + 1] - pos[i])
            return pr[i][0] + (pr[i + 1][0] - pr[i][0]) * t
    return pr[-1][0]


def mid_low(values: list[float], rows: Optional[list[dict]] = None) -> tuple[float, Optional[float]]:
    """(중앙값, 하위 25% — 4건 미만이면 None). rows 를 주고 BALANCE 가 켜져 있고 5건 넘는 단지가 있으면 단지 몫 상한을 적용"""
    ws = _weights(rows) if (BALANCE and rows is not None and len(rows) == len(values)) else None
    if ws and any(w < 1 for w in ws):
        return _wq(values, ws, 0.5), (_wq(values, ws, 0.25) if len(values) >= 4 else None)
    return statistics.median(values), (_p25(values) if len(values) >= 4 else None)


def capped(rows: list[dict]) -> list[tuple[str, int]]:
    """단지 몫 상한에 걸린 단지 (이름, 거래 수) — 근거 문구용"""
    if not BALANCE:
        return []
    n: dict = {}
    for r in rows:
        n.setdefault(complex_id(r), [r.get("apt", ""), 0])[1] += 1
    return sorted(((a, k) for a, k in n.values() if k > R.COMPLEX_CAP), key=lambda x: -x[1])


def cap_note(rows: list[dict]) -> str:
    c = capped(rows)
    if not c:
        return ""
    names = ", ".join(f"{a} {k}건" for a, k in c[:3]) + (f" 외 {len(c) - 3}곳" if len(c) > 3 else "")
    return f" · 거래가 몰린 단지({names})는 {R.COMPLEX_CAP}건 몫으로 줄여 계산"


def _summary(amounts_manwon: list[float], rows: Optional[list[dict]] = None) -> tuple[float, float]:
    med, p25 = mid_low(amounts_manwon, rows)
    base = med / 10000
    low = p25 / 10000 if p25 is not None else base * R.LOW_DISCOUNT
    return round(low, 2), round(base, 2)


def _ppa_summary(rows: list[dict], area: float) -> tuple[float, float]:
    """㎡당 가격 중앙값·하위 25% × 전용면적 (반올림 전 값, 억)"""
    med, p25 = mid_low([r["amount"] / r["area"] for r in rows], rows)
    base = med * area / 10000
    low = p25 * area / 10000 if p25 is not None else base * R.LOW_DISCOUNT
    return low, base


MAX_COMPS = 8


def _comp(r: dict, label: str, value_key: str) -> dict:
    """화면에 보여줄 근거 거래 한 건 (금액은 억 원)."""
    return {"apt": r.get("apt", ""), "umd": r.get("umd") or "", "area": r.get("area"), "floor": r.get("floor"), "dong": r.get("dong") or "",
            "amount": round((r.get(value_key) or 0) / 10000, 2), "date": r.get("date", ""),
            "kind": label, "direct": r.get("deal_type") == "직거래"}


def _recent(comps: list[dict]) -> list[dict]:
    return sorted(comps, key=lambda c: c["date"], reverse=True)[:MAX_COMPS]


def estimate_market(name: str, area: Optional[float], trades: list[dict], presales: list[dict],
                    this_year: int, area_fallback: bool = False, large_fallback: bool = False, unit: str = "", dong: str = "") -> dict:
    # 실제 시장 거래만 쓴다: 해제 거래는 parse_items 에서 이미 빠지고, 직거래(가족 간 저가 거래 등이 섞임)도 뺀다
    is_direct = lambda r: r.get("deal_type") == "직거래"
    newbuild = lambda r: bool(r.get("build_year")) and r["build_year"] >= this_year - R.NEW_BUILD_YEARS
    # 뺀 직거래 수는 실제로 비교 대상이 됐을 거래만 센다 (같은 단지·같은 평형, 없으면 같은 구 신축·같은 평형)
    own_direct = sum(1 for r in presales + trades
                     if is_direct(r) and r.get("amount") and same_complex(r["apt"], name, r.get("umd", ""), dong) and _in_band(r["area"], area))
    area_direct = sum(1 for r in trades if is_direct(r) and r.get("amount") and _in_band(r["area"], area) and newbuild(r))
    wide_direct = sum(1 for r in trades if is_direct(r) and r.get("amount") and r.get("area") and area and abs(r["area"] - area) <= R.AREA_BAND_WIDE and newbuild(r))
    trades = [r for r in trades if not is_direct(r)]
    presales = [r for r in presales if not is_direct(r)]
    # 분양권전매 API 의 ownershipGbn 은 '분'(분양권) / '입'(입주권) 약자로 온다 (2026-09-29 실제 응답)
    names = {"분": "분양권", "입": "입주권"}
    tagged = [(r, names.get(r.get("kind") or "", r.get("kind") or "분양권")) for r in presales] + [(r, "매매") for r in trades]
    own = [(r, k) for r, k in tagged if r.get("amount") and same_complex(r["apt"], name, r.get("umd", ""), dong) and _in_band(r["area"], area)]
    if own:
        low, base = _summary([r["amount"] for r, _ in own])
        return {"mkt_low": low, "mkt_base": base, "mkt_basis": "same_complex", "mkt_count": len(own),
                "mkt_comps": _recent([_comp(r, k, "amount") for r, k in own]),
                "mkt_direct_excluded": own_direct,
                "mkt_note": f"같은 단지 같은 평형 거래 {len(own)}건 기준 (최근 {R.MARKET_MONTHS}개월)"}
    comps = [r for r in trades
             if r.get("amount") and _in_band(r["area"], area)
             and r.get("build_year") and r["build_year"] >= this_year - R.NEW_BUILD_YEARS]
    if len(comps) >= 3:
        low, base = _summary([r["amount"] for r in comps], comps)
        return {"mkt_low": low, "mkt_base": base, "mkt_basis": "district_newbuild", "mkt_count": len(comps),
                "mkt_comps": _recent([_comp(r, "매매", "amount") for r in comps]),
                "mkt_direct_excluded": area_direct,
                "mkt_note": f"같은 구 준공 {R.NEW_BUILD_YEARS}년 이내 같은 평형 매매 {len(comps)}건 기준 (최근 {R.MARKET_MONTHS}개월){cap_note(comps)}"}
    # 기능 mkt_area_fallback (2026-10-07, evidence/qa/market-probe.txt): 같은 평형 거래가 3건 미만이면 같은 구 준공 10년 이내
    # 비슷한 면적(±10㎡) 매매의 ㎡당 가격 중앙값(보수: 하위 25%) × 이 주택형 전용면적. 107㎡처럼 거래가 드문 평형용 — '추정'으로 표시
    wide = [r for r in trades if area_fallback and area and r.get("amount") and r.get("area") and abs(r["area"] - area) <= R.AREA_BAND_WIDE and newbuild(r)]
    if len(wide) >= R.AREA_FALLBACK_MIN:
        low, base = _ppa_summary(wide, area)
        return {"mkt_low": round(low, 2), "mkt_base": round(base, 2), "mkt_basis": "district_area_ppa", "mkt_count": len(wide),
                "mkt_comps": _recent([_comp(r, "매매", "amount") for r in wide]),
                "mkt_direct_excluded": wide_direct,
                "mkt_note": f"같은 평형 거래가 부족해 같은 구 준공 {R.NEW_BUILD_YEARS}년 이내 비슷한 면적(±{R.AREA_BAND_WIDE:g}㎡) 매매 {len(wide)}건의 "
                            f"㎡당 가격 × 전용 {area:.1f}㎡로 추정 (최근 {R.MARKET_MONTHS}개월){cap_note(wide)}"}
    # 기능 mkt_large_fallback (2026-10-15 시세 부족 원인 분석, WORK.md): 큰 평형·새 구조라 같은/비슷한 면적 신축 거래가 없을 때
    #  ① 같은 단지(분양권·입주권 포함) 다른 평형 거래 3건 이상 → 그 ㎡당 가격 × 이 전용면적
    #  ② 전용 100㎡ 이상이면 같은 구 준공 10년 이내 100㎡ 이상 매매 5건 이상의 ㎡당 가격 × 이 전용면적
    #  펜트하우스(주택형 끝 P)는 값이 층·구조마다 제각각이라 추정하지 않는다. 보수 시세 = ㎡당 하위 25%(4건 미만이면 기준 × 0.9)
    penthouse = bool(re.search(r"P$", (unit or "").strip(), re.I))
    if large_fallback and area and not penthouse:
        def ppa_result(rows, basis, note, balance=False):
            rr = [r for r, _ in rows]
            if balance:   # 같은 구 100㎡ 이상(district_large_ppa)만 — 같은 단지 다른 평형은 한 단지라 그대로
                low, base = _ppa_summary(rr, area)
                note += cap_note(rr)
            else:
                ppa = [r["amount"] / r["area"] for r in rr]
                base = statistics.median(ppa) * area / 10000
                low = _p25(ppa) * area / 10000 if len(ppa) >= 4 else base * R.LOW_DISCOUNT
            return {"mkt_low": round(low, 2), "mkt_base": round(base, 2), "mkt_basis": basis, "mkt_count": len(rows),
                    "mkt_comps": _recent([_comp(r, k, "amount") for r, k in rows]), "mkt_direct_excluded": 0, "mkt_note": note}
        own_any = [(r, k) for r, k in tagged if r.get("amount") and r.get("area") and same_complex(r["apt"], name, r.get("umd", ""), dong)]
        if len(own_any) >= 3:
            return ppa_result(own_any, "same_complex_ppa", f"같은 평형 거래가 없어 같은 단지 다른 평형 거래 {len(own_any)}건의 ㎡당 가격 × 전용 {area:.1f}㎡로 추정 (최근 {R.MARKET_MONTHS}개월)")
        if area >= R.LARGE_AREA:
            big = [(r, "매매") for r in trades if r.get("amount") and r.get("area") and r["area"] >= R.LARGE_AREA and newbuild(r)]
            if len(big) >= R.AREA_FALLBACK_MIN:
                return ppa_result(big, "district_large_ppa", f"이 면적대 거래가 없어 같은 구 준공 {R.NEW_BUILD_YEARS}년 이내 전용 {R.LARGE_AREA:g}㎡ 이상 매매 {len(big)}건의 "
                                                              f"㎡당 가격 × 전용 {area:.1f}㎡로 추정 (최근 {R.MARKET_MONTHS}개월)", balance=True)
    return {"mkt_low": None, "mkt_base": None, "mkt_basis": None, "mkt_count": len(comps),
            "mkt_comps": _recent([_comp(r, "매매", "amount") for r in comps]),
            "mkt_direct_excluded": area_direct,
            "mkt_note": "비교할 거래가 부족해요" + shortage_reason(area, trades, this_year, penthouse) + ". 시세를 직접 확인하세요."}


def shortage_reason(area: Optional[float], trades: list[dict], this_year: int, penthouse: bool = False) -> str:
    """시세 부족 이유 한 마디 (화면 mkt_note) — 직거래를 뺀 최근 매매 기준"""
    new = [r for r in trades if r.get("amount") and r.get("build_year") and r["build_year"] >= this_year - R.NEW_BUILD_YEARS]
    band_old = sum(1 for r in trades if r.get("amount") and _in_band(r.get("area"), area)) - sum(1 for r in new if _in_band(r.get("area"), area))
    top = max((r["area"] for r in new if r.get("area")), default=None)
    if penthouse:
        return " — 펜트하우스형은 층·구조마다 값이 달라 비슷한 거래로 추정하지 않아요"
    if len(trades) < 10:
        return f" — 최근 {R.MARKET_MONTHS}개월 이 시군구 아파트 매매가 {len(trades)}건뿐이에요"
    if area and top and area > top + R.AREA_BAND_WIDE:
        return f" — 이 시군구 준공 {R.NEW_BUILD_YEARS}년 이내 매매는 전용 {top:.0f}㎡까지만 있어요"
    if band_old >= 3:
        return f" — 같은 평형 매매 {band_old}건은 모두 준공 {R.NEW_BUILD_YEARS}년이 넘은 단지라 새 아파트 시세로 쓰지 않았어요"
    return ""


def market_diag(name: str, area: Optional[float], trades: list[dict], presales: list[dict], this_year: int, dong: str = "") -> dict:
    """시세 부족 원인 기록용 건수 (2026-10-15 사용자 '시세부족 공고 원인 파악'). 계산에는 쓰지 않는다."""
    nd = [r for r in trades if r.get("deal_type") != "직거래" and r.get("amount")]
    new = [r for r in nd if r.get("build_year") and r["build_year"] >= this_year - R.NEW_BUILD_YEARS]
    near = lambda r, w: r.get("area") and area and abs(r["area"] - area) <= w
    return {"trades": len(nd), "newbuild": len(new), "band_any": sum(1 for r in nd if _in_band(r.get("area"), area)),
            "band_new": sum(1 for r in new if _in_band(r.get("area"), area)), "wide_new": sum(1 for r in new if near(r, R.AREA_BAND_WIDE)),
            "wide_any": sum(1 for r in nd if near(r, R.AREA_BAND_WIDE)),
            "own_any": sum(1 for r in presales + trades if r.get("amount") and same_complex(r.get("apt", ""), name, r.get("umd", ""), dong)),
            "max_area_new": max((r["area"] for r in new if r.get("area")), default=None)}


def estimate_jeonse(name: str, area: Optional[float], rents: list[dict], this_year: int, dong: str = "") -> dict:
    pool = [r for r in rents if r.get("deposit") and not r.get("monthly") and _in_band(r["area"], area)]
    own = [r for r in pool if same_complex(r["apt"], name, r.get("umd", ""), dong)]
    comps = own or [r for r in pool if r.get("build_year") and r["build_year"] >= this_year - R.NEW_BUILD_YEARS]
    shown = _recent([_comp(r, "전세", "deposit") for r in comps])
    if len(comps) < 3 and not own:
        return {"jeonse": None, "jeonse_note": "전세 거래가 부족해 추정하지 못했어요.", "jeonse_weak": True,
                "jeonse_comps": shown}
    v = statistics.median([r["deposit"] for r in comps]) / 10000 * R.JEONSE_MOVEIN_DISCOUNT
    src = "같은 단지" if own else f"같은 구 준공 {R.NEW_BUILD_YEARS}년 이내"
    return {"jeonse": round(v, 2),
            "jeonse_note": f"{src} 전세 {len(comps)}건 중앙값에서 입주장 할인 {int((1-R.JEONSE_MOVEIN_DISCOUNT)*100)}%",
            "jeonse_weak": len(comps) < 5, "jeonse_comps": shown}
